from ape import plugins
from ape.api import PluginConfig


class ZKSyncConfig(PluginConfig):
    ...


@plugins.register(plugins.Config)
def config_class():
    return ZKSyncConfig
