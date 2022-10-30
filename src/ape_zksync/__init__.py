from ape import plugins
from ape.api import create_network_type

from ape_zksync.account import ZKAccountContainer, ZKSyncAccount
from ape_zksync.compiler import ZKVyperCompiler
from ape_zksync.config import ZKSyncConfig
from ape_zksync.ecosystem import ZKSync
from ape_zksync.provider import ZKSyncProvider


@plugins.register(plugins.Config)
def config_class():
    return ZKSyncConfig


@plugins.register(plugins.CompilerPlugin)
def register_compiler():
    return (".zkvy",), ZKVyperCompiler


@plugins.register(plugins.EcosystemPlugin)
def ecosystems():
    yield ZKSync


@plugins.register(plugins.NetworkPlugin)
def networks():
    yield "zksync", "local", create_network_type(270, 270)
    yield "zksync", "testnet", create_network_type(280, 280)


@plugins.register(plugins.ProviderPlugin)
def providers():
    yield "zksync", "local", ZKSyncProvider
    yield "zksync", "testnet", ZKSyncProvider


@plugins.register(plugins.AccountPlugin)
def account_types():
    return ZKAccountContainer, ZKSyncAccount
