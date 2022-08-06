import sys
import time
from enum import Enum
from typing import IO, Iterator, List, Optional, Union

from ape.api import BlockAPI, ReceiptAPI
from ape.contracts.base import ContractEvent
from ape.exceptions import TransactionError
from ape.types import ContractLog
from ape.utils import ZERO_ADDRESS
from ape_ethereum.ecosystem import Ethereum
from ape_ethereum.transactions import Receipt, TransactionStatusEnum
from ethpm_types.abi import EventABI, EventABIType
from hexbytes import HexBytes
from pydantic import Field

from ape_zksync.config import ZKSyncConfig


class TransactionReceiptError(TransactionError):
    ...


class TransactionType(Enum):
    LEGACY = "0x"
    EIP712 = "0x71"


class ZKSyncBlock(BlockAPI):
    size: None = Field(None, exclude=True, repr=False)


class ZKSyncReceipt(ReceiptAPI):
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
    def total_fees_paid(self) -> int:
        # first transfer event is always fees paid
        event = next(
            self.decode_logs(
                EventABI(
                    type="event",
                    name="Transfer",
                    inputs=[
                        EventABIType(name="from", type="address", indexed=True),
                        EventABIType(name="from", type="address", indexed=True),
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

        receipt = ZKSyncReceipt(
            block_number=data.get("block_number") or data.get("blockNumber"),
            contract_address=data.get("contractAddress"),
            input=serialized_input,
            logs=data.get("logs", []),
            nonce=data["nonce"] if "nonce" in data and data["nonce"] != "" else None,
            receiver=data.get("to") or data.get("receiver") or "",
            required_confirmations=data.get("required_confirmations", 0),
            sender=data.get("sender") or data.get("from"),
            status=status,
            txn_hash=txn_hash,
            value=data.get("value", 0),
        )
        # TODO: decode serialized input for more info
        return receipt
