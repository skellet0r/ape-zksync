from ape import plugins
from ape.api import PluginConfig

from ape_zksync.compiler import ZKVyperCompiler


class ZKSyncConfig(PluginConfig):
    ...


@plugins.register(plugins.Config)
def config_class():
    return ZKSyncConfig


@plugins.register(plugins.CompilerPlugin)
def register_compiler():
    return (".zkvy",), ZKVyperCompiler
