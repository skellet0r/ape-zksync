import sys
import time
from enum import Enum
from hashlib import sha256
from typing import IO, Iterator, List, Optional, Tuple, Union

import rlp
from ape.api import BlockAPI, ReceiptAPI, TransactionAPI
from ape.contracts.base import ContractEvent
from ape.exceptions import OutOfGasError, SignatureError, TransactionError
from ape.types import ContractLog, TransactionSignature
from ape.utils import EMPTY_BYTES32, ZERO_ADDRESS
from ape_ethereum.ecosystem import Ethereum
from ape_ethereum.transactions import BaseTransaction, Receipt, TransactionStatusEnum
from ethpm_types.abi import ABIType, ConstructorABI, EventABI, EventABIType, MethodABI
from hexbytes import HexBytes
from pydantic import Field

from ape_zksync.config import ZKSyncConfig

CONTRACT_DEPLOYER_ADDRESS = "0x0000000000000000000000000000000000008006"


class ZKSyncTransaction(BaseTransaction):
    type: int = 0x71
    gas_price: int
    fee_token: str = ZERO_ADDRESS
    ergs_per_pub_data: int = 0
    factory_deps: Optional[List[bytes]] = None
    aa_params: Optional[Tuple[str, TransactionSignature]] = None

    max_fee: Optional[int] = Field(None, exclude=True, repr=False)
    max_priority_fee: Optional[int] = Field(None, exclude=True, repr=False)

    def serialize_transaction(self) -> bytes:
        # NOTE: AA transactions aren't supported currently
        # if self.signature is None, aa_params[1] should be a sig == AA tx
        if not self.signature:
            raise SignatureError("The transaction is not signed.")

        data = list(
            map(
                lambda v: HexBytes("0x") if v == 0 else HexBytes(v),
                # HexBytes,
                [
                    self.nonce,
                    self.gas_price,
                    self.gas_limit,
                    self.receiver,
                    self.value,
                    self.data,
                    self.signature.v - 27,
                    self.signature.r,
                    self.signature.s,
                    self.chain_id,
                    self.fee_token,
                    self.ergs_per_pub_data,
                ],
            )
        ) + [
            list(map(HexBytes, self.factory_deps or [])),
            list(map(HexBytes, self.aa_params or [])),
        ]
        return HexBytes(0x71) + rlp.encode(data)

    @property
    def total_transfer_value(self) -> int:
        return self.gas_limit * self.gas_price + self.value


class TransactionReceiptError(TransactionError):
    ...


class TransactionType(Enum):
    LEGACY = "0x"
    EIP712 = "0x71"


class ZKSyncBlock(BlockAPI):
    size: None = Field(None, exclude=True, repr=False)


class ZKSyncReceipt(ReceiptAPI):
    # TODO: also include Account Abstraction data
    gas_limit: int = 0
    gas_price: int = 0
    gas_used: int = 0

    # serialized tx submitted to the network
    tx_type: TransactionType = TransactionType.LEGACY
    input: bytes

    # replaces gas fields in EIP712 txs
    ergs_limit: int = 0
    ergs_per_pubdata_byte_limit: int = 0
    ergs_price: int = 0

    # zksync allows paying in tokens as well as ETH
    fee_token: str = ZERO_ADDRESS

    @property
    def failed(self) -> bool:
        return self.status == TransactionStatusEnum.FAILING

    @property
    def ran_out_of_gas(self) -> bool:
        return self.failed and self.gas_used == (self.gas_limit or self.ergs_limit)

    def raise_for_status(self):
        if self.ran_out_of_gas:
            raise OutOfGasError()
        elif self.failed:
            txn_hash = HexBytes(self.txn_hash).hex()
            raise TransactionError(message=f"Transaction '{txn_hash}' failed.")

    @property
    def total_fees_paid(self) -> int:
        # first transfer event is always fees paid
        event = next(
            self.decode_logs(
                EventABI(
                    type="event",
                    name="Transfer",
                    inputs=[
                        EventABIType(name="from", type="address", indexed=True),
                        EventABIType(name="to", type="address", indexed=True),
                        EventABIType(name="value", type="uint256"),
                    ],
                )
            )
        )
        return event.value

    def decode_logs(
        self,
        abi: Optional[
            Union[List[Union[EventABI, ContractEvent]], Union[EventABI, ContractEvent]]
        ] = None,
    ) -> Iterator[ContractLog]:
        return Receipt.decode_logs(self, abi)

    def show_trace(self, verbose: bool = False, file: IO[str] = sys.stdout):
        Receipt.show_trace(self, verbose, file)


class ZKSync(Ethereum):
    name = "zksync"

    @property
    def config(self) -> ZKSyncConfig:
        return self.config_manager.get_config("zksync")

    def decode_block(self, data: dict) -> ZKSyncBlock:
        return ZKSyncBlock.parse_obj(data)

    def decode_receipt(self, data: dict) -> ZKSyncReceipt:
        # NOTE: receipt data can be returned with status and block_number set to None
        # keep polling until we get valid values.
        # TODO: make this configurable via the ZKSyncConfig class
        loops = 0
        while data["blockNumber"] is None:
            if loops == 32:  # NOTE: magic number (could be anything)
                raise TransactionReceiptError(message=f"Status pending for tx: {data['hash']}")
            time.sleep(0.25)
            data.update(self.provider.web3.eth.get_transaction_receipt(data["hash"]))

        # copied over from Ethereum ecosystem class
        status = data.get("status")
        if status:
            if isinstance(status, str) and status.isnumeric():
                status = int(status)

            status = TransactionStatusEnum(status)

        txn_hash = HexBytes(data.get("hash", b"")).hex()
        # NOTE: to get calldata we need to actually decode the serialized tx
        serialized_input = HexBytes(data.get("input", ""))
        decoded_input = []

        tx_type = TransactionType.LEGACY
        if hex(serialized_input[0]) == TransactionType.EIP712.value:
            tx_type = TransactionType.EIP712
            decoded_input = [
                HexBytes(i).hex() if isinstance(i, (bytes, int)) else i
                for i in rlp.decode(serialized_input[1:])
            ]
        else:
            decoded_input = [HexBytes(i).hex() for i in rlp.decode(serialized_input)]

        calldata = HexBytes(decoded_input[5])
        gas_limit = 0 if decoded_input[2] == "0x" else int(decoded_input[2], 16)
        gas_price = 0 if decoded_input[1] == "0x" else int(decoded_input[1], 16)
        fee_token = ZERO_ADDRESS
        ergs_limit = 0
        ergs_per_pubdata_byte_limit = 0
        ergs_price = 0

        if tx_type == TransactionType.EIP712:
            fee_token = decoded_input[10]
            ergs_per_pubdata_byte_limit = (
                0 if decoded_input[11] == "0x" else int(decoded_input[11], 16)
            )
            if ergs_per_pubdata_byte_limit != 0:
                ergs_limit = gas_limit
                ergs_price = gas_price

                gas_limit = 0
                gas_price = 0

        receipt = ZKSyncReceipt(
            block_number=data.get("block_number") or data.get("blockNumber"),
            contract_address=data.get("contractAddress"),
            data=calldata,
            ergs_limit=ergs_limit,
            ergs_per_pubdata_byte_limit=ergs_per_pubdata_byte_limit,
            ergs_price=ergs_price,
            fee_token=fee_token,
            gas_limit=gas_limit,
            gas_price=gas_price,
            input=serialized_input,
            logs=data.get("logs", []),
            nonce=data["nonce"] if "nonce" in data and data["nonce"] != "" else None,
            receiver=data.get("to") or data.get("receiver") or "",
            required_confirmations=data.get("required_confirmations", 0),
            sender=data.get("sender") or data.get("from"),
            status=status,
            tx_type=tx_type,
            txn_hash=txn_hash,
            value=data.get("value", 0),
        )
        receipt.gas_used = receipt.total_fees_paid // (gas_price or ergs_price)
        return receipt

    def encode_deployment(
        self, deployment_bytecode: HexBytes, abi: ConstructorABI, *args, **kwargs
    ) -> ZKSyncTransaction:
        assert len(deployment_bytecode) < 2**16
        # contract deployments require a tx to the Contract Deployer contract
        create_abi = MethodABI(
            type="function",
            name="create",
            inputs=[
                ABIType(type="bytes32"),
                ABIType(type="bytes32"),
                ABIType(type="uint256"),
                ABIType(type="bytes"),
            ],
            outputs=[ABIType(type="address")],
        )
        # bytecodehash passed as an argument is the sha256 hash of the
        # init code, where the upper 2 bytes are the word length of the init code
        bytecode_hash = sha256(deployment_bytecode).hexdigest()  # doesn't have leading 0x
        bytecode_hash = "0x" + hex(len(deployment_bytecode) // 32)[2:].zfill(4) + bytecode_hash[4:]
        create_args = [
            HexBytes(EMPTY_BYTES32),
            HexBytes(bytecode_hash),
            kwargs["value"],
            self.encode_calldata(abi, *args) if abi.inputs else b"",
        ]

        # modify kwargs
        kwargs["type"] = 0x71
        kwargs["factory_deps"] = [deployment_bytecode] + kwargs.get("factory_deps", [])
        kwargs.setdefault("gas_price", self.provider.gas_price)
        kwargs["chain_id"] = self.provider.chain_id

        return super().encode_transaction(
            CONTRACT_DEPLOYER_ADDRESS, create_abi, *create_args, **kwargs
        )

    def create_transaction(self, **kwargs) -> TransactionAPI:
        if kwargs.setdefault("type", 0) == 0:
            return super().create_transaction(**kwargs)
        else:
            kwargs["type"] = 0x71
            if kwargs.get("required_confirmations") is None:
                # Attempt to use default required-confirmations from `ape-config.yaml`.
                required_confirmations = 0
                active_provider = self.network_manager.active_provider
                if active_provider:
                    required_confirmations = active_provider.network.required_confirmations

                kwargs["required_confirmations"] = required_confirmations

            # use eip712 transaction type
            return ZKSyncTransaction(**kwargs)
