from ape import plugins

from ape_zksync_test.account import TestAccount, TestAccountContainer


@plugins.register(plugins.AccountPlugin)
def account_types():
    return TestAccountContainer, TestAccount
