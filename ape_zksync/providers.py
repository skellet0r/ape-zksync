from ape.api import Web3Provider
from ape.exceptions import ProviderError
from web3 import HTTPProvider, Web3


class ZKSyncProviderError(ProviderError):
    ...


class ZKSyncProvider(Web3Provider):
    name = "zksync"

    @property
    def uri(self) -> str:
        if self.network.name == "testnet":
            return "https://zksync2-testnet.zksync.dev"
        raise ZKSyncProviderError(f"Unknown network: {self.network.name}")

    @property
    def gas_price(self) -> int:
        return self.web3.eth.gas_price

    def connect(self):
        self._web3 = Web3(HTTPProvider(self.uri))

    def disconnect(self):
        self._web3 = None
