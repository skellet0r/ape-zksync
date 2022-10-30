from pathlib import Path

from ape_zksync_test.account import TestAccount, TestAccountContainer

container = TestAccountContainer.parse_obj(
    {"data_folder": Path(__file__).parent / "data", "account_type": TestAccount}
)
