from hashlib import sha256
from typing import Dict, Optional

from ape.api import BlockAPI, TransactionAPI, Web3Provider
from ape.utils import EMPTY_BYTES32
from ape_ethereum.ecosystem import Ethereum
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
        if self.network.name == "testnet":
            return "http://localhost:3050"
        raise Exception(f"Unknown network: {self.network.name}")

    @property
    def gas_price(self) -> int:
        return self.web3.eth.gas_price

    def connect(self):
        self._web3 = Web3(HTTPProvider(self.uri))

    def disconnect(self):
        self._web3 = None


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
        receipt = ZKSyncReceipt.parse_obj(data)
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

    def encode_deployment(
        self, deployment_bytecode: HexBytes, abi: ConstructorABI, *args, **kwargs
    ) -> ZKSyncTransaction:
        # contract deployments require a tx to the Contract Deployer contract
        create_abi = CONTRACT_DEPLOYER_TYPE.mutable_methods["create"]

        # bytecodehash passed as an argument is the sha256 hash of the
        # init code, where the upper 2 bytes are the word length of the init code
        bytecode_hash = sha256(
            deployment_bytecode
        ).hexdigest()  # doesn't have leading 0x
        bytecode_hash = (
            "0x" + hex(len(deployment_bytecode) // 32)[2:].zfill(4) + bytecode_hash[4:]
        )
        create_args = [
            HexBytes(EMPTY_BYTES32),
            HexBytes(bytecode_hash),
            kwargs["value"],
            self.encode_calldata(abi, *args) if abi.inputs else b"",
        ]

        # modify kwargs
        kwargs.setdefault("type", TransactionType.ZKSYNC.value)
        kwargs["factory_deps"] = [deployment_bytecode] + kwargs.get("factory_deps", [])
        kwargs.setdefault("gas_price", self.provider.gas_price)
        kwargs["chain_id"] = self.provider.chain_id

        return super().encode_transaction(
            CONTRACT_DEPLOYER, create_abi, *create_args, **kwargs
        )

    def create_transaction(self, **kwargs) -> TransactionAPI:
        if (
            kwargs.setdefault("type", TransactionType.LEGACY.value)
            == TransactionType.LEGACY.value
        ):
            return LegacyTransaction.parse_obj(kwargs)
        elif kwargs["type"] == TransactionType.ZKSYNC.value:
            return ZKSyncTransaction.parse_obj(kwargs)

        raise Exception()
