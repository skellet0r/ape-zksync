from ape.api import BlockAPI
from pydantic import Field, validator


class ZKSyncBlock(BlockAPI):
    base_fee_per_gas: int
    l1_batch_number: int

    size: int = Field(0, exclude=True)

    @validator("l1_batch_number", pre=True)
    def to_int(self, value):
        return int(value, 16)
