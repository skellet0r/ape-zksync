from ape import plugins
from ape.api import create_network_type

from ape_zksync.accounts import ZKAccountContainer, ZKSyncAccount
from ape_zksync.config import ZKSyncConfig
from ape_zksync.ecosystems import ZKSync
from ape_zksync.providers import ZKSyncProvider


@plugins.register(plugins.Config)
def config_class():
    return ZKSyncConfig


@plugins.register(plugins.EcosystemPlugin)
def ecosystems():
    yield ZKSync


@plugins.register(plugins.NetworkPlugin)
def networks():
    yield "zksync", "testnet", create_network_type(280, 280)


@plugins.register(plugins.ProviderPlugin)
def providers():
    yield "zksync", "testnet", ZKSyncProvider


@plugins.register(plugins.AccountPlugin)
def account_types():
    return ZKAccountContainer, ZKSyncAccount
