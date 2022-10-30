import time
from typing import Dict, Optional

from ape.api import BlockAPI, TransactionAPI
from ape.exceptions import TransactionError
from ape.types import AddressType
from ape.utils import EMPTY_BYTES32
from ape_ethereum.ecosystem import Ethereum, ProxyInfo
from ethpm_types.abi import ConstructorABI
from hexbytes import HexBytes
from pydantic import Field, validator

from ape_zksync.config import ZKSyncConfig
from ape_zksync.constants import CONTRACT_DEPLOYER, CONTRACT_DEPLOYER_TYPE
from ape_zksync.transaction import (
    LegacyTransaction,
    TransactionType,
    ZKSyncReceipt,
    ZKSyncTransaction,
)
from ape_zksync.utils import hash_bytecode


class ZKSyncBlock(BlockAPI):
    base_fee_per_gas: int = Field(..., alias="baseFeePerGas")
    l1_batch_number: int = Field(..., alias="l1BatchNumber")

    size: Optional[int] = Field(None, exclude=True)

    @validator("l1_batch_number", pre=True)
    def to_int(cls, value):
        return int(value, 16)


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
        receipt = ZKSyncReceipt.parse_obj({"transaction": self.create_transaction(**data), **data})
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
            receipt.contract_address = deployment.contractAddress
        return receipt

    def get_proxy_info(self, address: AddressType) -> Optional[ProxyInfo]:
        return None

    def encode_deployment(
        self, deployment_bytecode: HexBytes, abi: ConstructorABI, *args, **kwargs
    ) -> ZKSyncTransaction:
        # contract deployments require a tx to the Contract Deployer contract
        create_abi = CONTRACT_DEPLOYER_TYPE.mutable_methods["create"]

        # bytecodehash passed as an argument is the sha256 hash of the
        # init code, where the upper 2 bytes are the word length of the init code
        bytecode_hash = hash_bytecode(deployment_bytecode)
        create_args = [
            HexBytes(EMPTY_BYTES32),
            HexBytes(bytecode_hash),
            self.encode_calldata(abi, *args) if abi.inputs else b"",
        ]

        # modify kwargs
        kwargs["type"] = TransactionType.ZKSYNC.value
        kwargs["factory_deps"] = [deployment_bytecode.hex()] + [
            HexBytes(v).hex() for v in kwargs.get("factory_deps", [])
        ]
        kwargs.setdefault("gas_price", self.provider.gas_price)
        kwargs["chain_id"] = self.provider.chain_id

        return super().encode_transaction(CONTRACT_DEPLOYER, create_abi, *create_args, **kwargs)

    def create_transaction(self, **kwargs) -> TransactionAPI:
        if kwargs.setdefault("type", TransactionType.ZKSYNC.value) == TransactionType.ZKSYNC.value:
            return ZKSyncTransaction.parse_obj(kwargs)
        elif kwargs["type"] == TransactionType.LEGACY.value:
            return LegacyTransaction.parse_obj(kwargs)

        raise Exception()
