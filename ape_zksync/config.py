from typing import Optional

from ape.api import PluginConfig

DEFAULT_TRANSACTION_ACCEPTANCE_TIMEOUT = 120


class NetworkConfig(PluginConfig):
    block_time: int = 0
    default_provider: Optional[str] = None
    required_confirmations: int = 0
    transaction_acceptance_timeout: int = DEFAULT_TRANSACTION_ACCEPTANCE_TIMEOUT


class ZKSyncConfig(PluginConfig):
    testnet: NetworkConfig = NetworkConfig(block_time=5, required_confirmations=1)
    default_network: str = "testnet"
