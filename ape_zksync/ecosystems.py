from ape.api import BlockAPI
from pydantic import Field


class ZKSyncBlock(BlockAPI):
    size: None = Field(None, exclude=True, repr=False)
