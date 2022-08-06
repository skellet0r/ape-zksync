from ape.api import BlockAPI
from ape_ethereum.ecosystem import Ethereum
from pydantic import Field

from ape_zksync.config import ZKSyncConfig


class ZKSyncBlock(BlockAPI):
    size: None = Field(None, exclude=True, repr=False)


class ZKSync(Ethereum):
    name = "zksync"

    @property
    def config(self) -> ZKSyncConfig:
        return self.config_manager.get_config("zksync")

    def decode_block(self, data: dict) -> ZKSyncBlock:
        return ZKSyncBlock.parse_obj(data)
