from ape import plugins

from ape_zksync.config import ZKSyncConfig


@plugins.register(plugins.Config)
def config_class():
    return ZKSyncConfig
