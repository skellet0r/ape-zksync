from typing import Iterator, List, Optional, Union

from ape.api import BlockAPI, ReceiptAPI
from ape.base import ContractEvent
from ape.types import ContractLog
from ape_ethereum.ecosystem import Ethereum
from ape_ethereum.transactions import Receipt
from ethpm_types.abi import EventABI, EventABIType
from pydantic import Field

from ape_zksync.config import ZKSyncConfig


class ZKSyncBlock(BlockAPI):
    size: None = Field(None, exclude=True, repr=False)


class ZKSyncReceipt(ReceiptAPI):
    gas_limit: int = Field(0, exclude=True)
    gas_price: int = Field(0, exclude=True)
    gas_used: int = Field(0, exclude=True)

    # serialized tx submitted to the network
    tx_type: int
    input: bytes

    # replaces gas fields in EIP712 txs
    ergs_limit: int = 0
    ergs_per_pubdata_byte_limit: int = 0
    ergs_price: int = 0

    # zksync allows paying in tokens as well as ETH
    fee_token: str

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


class ZKSync(Ethereum):
    name = "zksync"

    @property
    def config(self) -> ZKSyncConfig:
        return self.config_manager.get_config("zksync")

    def decode_block(self, data: dict) -> ZKSyncBlock:
        return ZKSyncBlock.parse_obj(data)
