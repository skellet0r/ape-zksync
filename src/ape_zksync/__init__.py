from ape import plugins

from ape_zksync.compiler import ZKVyperCompiler
from ape_zksync.config import ZKSyncConfig


@plugins.register(plugins.Config)
def config_class():
    return ZKSyncConfig


@plugins.register(plugins.CompilerPlugin)
def register_compiler():
    return (".zkvy",), ZKVyperCompiler
