import enum
from typing import List, Optional

from ape.api import TransactionAPI
from ape.types import AddressType, GasLimit
from eth_typing import Hash32
from pydantic import Field


class TransactionType(enum.IntEnum):
    ZKSYNC = 0x71


class ZKSyncTransaction(TransactionAPI):
    """ZKSync Transaction"""

    gas_per_pubdata_byte_limit: int = Field(160_000, alias="ergsPerPubdataByteLimit")
    paymaster: Optional[AddressType] = None
    factory_dependencies: Optional[List[Hash32]] = Field(None, alias="factoryDeps")
    paymaster_input: Optional[bytes] = Field(None, alias="paymasterInput")

    gas_limit: Optional[GasLimit] = Field(None, alias="ergsLimit")
    type: TransactionType = Field(TransactionType.ZKSYNC, alias="txType", const=True)
    max_fee: Optional[int] = Field(None, alias="maxFeePerErg")
    max_priority_fee: Optional[int] = Field(None, alias="maxPriorityFeePerErg")
