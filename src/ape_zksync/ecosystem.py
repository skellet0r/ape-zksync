import time
from hashlib import sha256
from typing import AnyStr, Dict, Optional

from ape.api import BlockAPI, TransactionAPI, Web3Provider
from ape.exceptions import TransactionError
from ape.utils import EMPTY_BYTES32
from ape_ethereum.ecosystem import Ethereum
from eth_typing import Hash32
from ethpm_types.abi import ConstructorABI
from hexbytes import HexBytes
from pydantic import Field, validator
from web3 import HTTPProvider, Web3

from ape_zksync.config import ZKSyncConfig
from ape_zksync.constants import CONTRACT_DEPLOYER, CONTRACT_DEPLOYER_TYPE
from ape_zksync.transaction import (
    LegacyTransaction,
    TransactionType,
    ZKSyncReceipt,
    ZKSyncTransaction,
)


class ZKSyncBlock(BlockAPI):
    base_fee_per_gas: int = Field(..., alias="baseFeePerGas")
    l1_batch_number: int = Field(..., alias="l1BatchNumber")

    size: Optional[int] = Field(None, exclude=True)

    @validator("l1_batch_number", pre=True)
    def to_int(cls, value):
        return int(value, 16)


class ZKSyncProvider(Web3Provider):
    name = "zksync"

    @property
    def uri(self) -> str:
        if self.network.name == "local":
            return "http://localhost:3050"
        elif self.network.name == "testnet":
            return "https://zksync2-testnet.zksync.dev"
        raise Exception(f"Unknown network: {self.network.name}")

    @property
    def gas_price(self) -> int:
        return self.web3.eth.gas_price

    def connect(self):
        self._web3 = Web3(HTTPProvider(self.uri))

    def disconnect(self):
        self._web3 = None

    def prepare_transaction(self, txn: TransactionAPI) -> TransactionAPI:
        txn.chain_id = self.network.chain_id

        txn_type = TransactionType(txn.type)
        if (
            txn_type == TransactionType.LEGACY
            and isinstance(txn, LegacyTransaction)
            and txn.gas_price is None
        ):
            txn.gas_price = self.gas_price
        elif txn_type == TransactionType.ZKSYNC:
            txn.max_fee = self.gas_price

        gas_limit = txn.gas_limit or self.network.gas_limit
        if isinstance(gas_limit, str) and gas_limit.isnumeric():
            txn.gas_limit = int(gas_limit)
        elif isinstance(gas_limit, str) and gas_limit.startswith("0x"):
            txn.gas_limit = int(gas_limit, 16)
        elif gas_limit == "max":
            txn.gas_limit = self.max_gas
        elif gas_limit in ("auto", None):
            txn.gas_limit = self.estimate_gas_cost(txn)
        else:
            txn.gas_limit = gas_limit

        assert txn.gas_limit not in ("auto", "max")
        # else: Assume user specified the correct amount or txn will fail and waste gas

        if txn.required_confirmations is None:
            txn.required_confirmations = self.network.required_confirmations
        elif (
            not isinstance(txn.required_confirmations, int)
            or txn.required_confirmations < 0
        ):
            raise TransactionError(
                message="'required_confirmations' must be a positive integer."
            )

        return txn


class ZKSync(Ethereum):
    name = "zksync"

    @property
    def config(self) -> ZKSyncConfig:
        return super(Ethereum, self).config

    def serialize_transaction(self, transaction: TransactionAPI) -> bytes:
        return transaction.serialize_transaction()

    def decode_block(self, data: Dict) -> BlockAPI:
        data["num_transactions"] = len(data["transactions"])
        return ZKSyncBlock.parse_obj(data)

    def decode_receipt(self, data: dict) -> ZKSyncReceipt:
        loops = 0
        while data["blockNumber"] is None:
            if loops == 32:  # NOTE: magic number (could be anything)
                raise TransactionError(message=f"Status pending for tx: {data['hash']}")
            time.sleep(0.25)
            data.update(self.provider.web3.eth.get_transaction_receipt(data["hash"]))

        data["transactionHash"] = data.get("transactionHash", b"").hex()
        receipt = ZKSyncReceipt.parse_obj(
            {"transaction": self.create_transaction(**data), **data}
        )
        deployment = next(
            (
                log
                for log in receipt.decode_logs()
                if log.contract_address == CONTRACT_DEPLOYER
                and log.event_name == "ContractDeployed"
            ),
            None,
        )
        if deployment:
            receipt.contract_address = deployment
        return receipt

    @staticmethod
    def hash_bytecode(bytecode: AnyStr) -> "Hash32":
        # bytecodehash passed as an argument is the sha256 hash of the
        # init code, where the upper 2 bytes are the word length of the init code
        bytecode = HexBytes(bytecode)  # type: ignore
        bytecode_hash = sha256(
            bytecode  # type: ignore
        ).hexdigest()  # doesn't have leading 0x  # type: ignore
        bytecode_hash = "0x" + hex(len(bytecode) // 32)[2:].zfill(4) + bytecode_hash[4:]
        return HexBytes(bytecode_hash)

    def encode_deployment(
        self, deployment_bytecode: HexBytes, abi: ConstructorABI, *args, **kwargs
    ) -> ZKSyncTransaction:
        # contract deployments require a tx to the Contract Deployer contract
        create_abi = CONTRACT_DEPLOYER_TYPE.mutable_methods["create"]

        # bytecodehash passed as an argument is the sha256 hash of the
        # init code, where the upper 2 bytes are the word length of the init code
        bytecode_hash = self.hash_bytecode(deployment_bytecode)
        create_args = [
            HexBytes(EMPTY_BYTES32),
            HexBytes(bytecode_hash),
            self.encode_calldata(abi, *args) if abi.inputs else b"",
        ]

        # modify kwargs
        kwargs.setdefault("type", TransactionType.ZKSYNC.value)
        kwargs["factory_deps"] = [HexBytes(deployment_bytecode)] + kwargs.get(
            "factory_deps", []
        )
        kwargs.setdefault("gas_price", self.provider.gas_price)
        kwargs["chain_id"] = self.provider.chain_id

        return super().encode_transaction(
            CONTRACT_DEPLOYER, create_abi, *create_args, **kwargs
        )

    def create_transaction(self, **kwargs) -> TransactionAPI:
        if (
            kwargs.setdefault("type", TransactionType.ZKSYNC.value)
            == TransactionType.ZKSYNC.value
        ):
            return ZKSyncTransaction.parse_obj(kwargs)
        elif kwargs["type"] == TransactionType.LEGACY.value:
            return LegacyTransaction.parse_obj(kwargs)

        raise Exception()
