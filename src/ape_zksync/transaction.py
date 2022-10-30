import enum
from typing import Iterator, List, Optional, Union

import rlp
from ape.api import ReceiptAPI, TransactionAPI
from ape.contracts import ContractEvent
from ape.exceptions import SignatureError
from ape.types import AddressType, ContractLog, GasLimit, MessageSignature
from ape_ethereum.transactions import Receipt, StaticFeeTransaction
from eth_typing import Hash32
from eth_utils import keccak
from ethpm_types.abi import EventABI
from hexbytes import HexBytes
from pydantic import Field, validator

from ape_zksync.constants import (
    CONTRACT_DEPLOYER_TYPE,
    DEFAULT_GAS_PER_PUBDATA_BYTE_LIMIT,
    ERC20_TYPE,
)
from ape_zksync.utils import to_bytes


class TransactionStatus(enum.IntEnum):
    FAILED = 0
    SUCCESS = 1


class TransactionType(enum.IntEnum):
    LEGACY = 0x00
    ZKSYNC = 0x71


class LegacyTransaction(StaticFeeTransaction):
    """Legacy Ethereum Transaction"""

    type: int = Field(TransactionType.LEGACY.value, exclude=True, const=True)


class ZKSyncTransaction(TransactionAPI):
    """ZKSync Transaction"""

    gas_per_pubdata_byte_limit: int = Field(
        DEFAULT_GAS_PER_PUBDATA_BYTE_LIMIT, alias="ergsPerPubdataByteLimit"
    )
    paymaster: Optional[AddressType] = None
    factory_deps: List[bytes] = Field(default_factory=list, alias="factoryDeps")
    paymaster_input: Optional[bytes] = Field(None, alias="paymasterInput")

    gas_limit: Optional[GasLimit] = Field(None, alias="ergsLimit")
    type: int = Field(TransactionType.ZKSYNC.value, alias="txType", const=True)
    max_fee: Optional[int] = Field(None, alias="maxFeePerErg")
    max_priority_fee: int = Field(0, alias="maxPriorityFeePerErg")

    signature: Optional[Union[MessageSignature, bytes]] = Field(None, exclude=True)

    def serialize_transaction(self) -> bytes:
        if not self.signature:
            raise SignatureError("Transaction is not signed.")

        data = [
            to_bytes(self.nonce),
            to_bytes(self.max_priority_fee),
            to_bytes(self.max_fee),
            to_bytes(self.gas_limit),
            HexBytes(self.receiver),
            to_bytes(self.value),
            HexBytes(self.data),
        ]

        if isinstance(self.signature, MessageSignature):
            v, r, s = self.signature
            data += [to_bytes(v - 27), to_bytes(r), to_bytes(s)]
        else:
            # account abstraction support
            data += [to_bytes(self.chain_id), b"", b""]

        data += [
            to_bytes(self.chain_id),
            HexBytes(self.sender),
            to_bytes(self.gas_per_pubdata_byte_limit),
            [HexBytes(v) for v in self.factory_deps] if self.factory_deps else [],
            to_bytes(self.signature if isinstance(self.signature, bytes) else b""),
        ]

        if self.paymaster:
            data += [[HexBytes(self.paymaster), to_bytes(self.paymaster_input)]]
        else:
            data += [[]]

        return HexBytes(self.type) + rlp.encode(data)

    @property
    def txn_hash(self) -> HexBytes:
        return HexBytes(keccak(self.serialize_transaction()))


class ZKSyncReceipt(ReceiptAPI):
    block_hash: Hash32 = Field(..., alias="blockHash")
    block_number: int = Field(..., alias="blockNumber")
    contract_address: Optional[AddressType] = Field(None, alias="contractAddress")
    gas_price: int = Field(..., alias="effectiveGasPrice")
    sender: AddressType = Field(..., alias="from")
    gas_used: int = Field(..., alias="gasUsed")
    l1_batch_number: Optional[int] = Field(..., alias="l1BatchNumber")
    l1_batch_tx_index: Optional[int] = Field(..., alias="l1BatchTxIndex")
    txn_hash: str = Field(..., alias="transactionHash")
    type: int = 0

    @validator("l1_batch_number", "l1_batch_tx_index", pre=True)
    def to_int(cls, value):
        if value:
            return int(value, 16)
        return value

    @property
    def total_fees_paid(self) -> int:
        # first log emitted is always ETH token tx fee
        # NOTE: tx fee can be paid in tokens other than ETH
        return next(self.decode_logs()).value

    @property
    def ran_out_of_gas(self) -> bool:
        return (
            self.status == TransactionStatus.FAILED and self.gas_used == self.transaction.gas_limit
        )

    def decode_logs(
        self,
        abi: Optional[
            Union[List[Union[EventABI, ContractEvent]], Union[EventABI, ContractEvent]]
        ] = None,
    ) -> Iterator[ContractLog]:
        if abi is None:
            abi = []
        elif not isinstance(abi, (list, tuple)):
            abi = [abi]

        abi += [ERC20_TYPE.events["Transfer"]]
        abi += [CONTRACT_DEPLOYER_TYPE.events["ContractDeployed"]]

        yield from Receipt.decode_logs(self, abi)
        yield from Receipt.decode_logs(self)

    _decode_ds_note = Receipt._decode_ds_note
