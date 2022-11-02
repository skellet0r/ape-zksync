from ape.api import TransactionAPI, Web3Provider
from ape.exceptions import TransactionError
from web3 import HTTPProvider, Web3

from ape_zksync.transaction import LegacyTransaction, TransactionType
from ape_zksync.constants import CONTRACT_DEPLOYER


class ZKSyncProvider(Web3Provider):
    name = "zksync"

    @property
    def uri(self) -> str:
        if self.network.name == "testnet":
            return "https://zksync2-testnet.zksync.dev"
        elif self.network.name == "local":
            return "http://localhost:3050"
        raise Exception(f"Unknown network: {self.network.name}")

    @property
    def gas_price(self) -> int:
        return self.web3.eth.gas_price

    def connect(self):
        self._web3 = Web3(HTTPProvider(self.uri))

    def disconnect(self):
        self._web3 = None

    def prepare_transaction(self, txn: TransactionAPI) -> TransactionAPI:
        txn.chain_id = self.network.chain_id

        txn_type = TransactionType(txn.type)
        if (
            txn_type == TransactionType.LEGACY
            and isinstance(txn, LegacyTransaction)
            and txn.gas_price is None
        ):
            txn.gas_price = self.gas_price
        elif txn_type == TransactionType.ZKSYNC and txn.max_fee is None:
            txn.max_fee = self.gas_price

        gas_limit = txn.gas_limit or self.network.gas_limit
        if isinstance(gas_limit, str) and gas_limit.isnumeric():
            txn.gas_limit = int(gas_limit)
        elif isinstance(gas_limit, str) and gas_limit.startswith("0x"):
            txn.gas_limit = int(gas_limit, 16)
        elif gas_limit == "max":
            txn.gas_limit = self.max_gas
        elif gas_limit in ("auto", None):
            txn.gas_limit = self.estimate_gas_cost(txn)
            # TODO: figure why gas estimates are so low for first time deployments
            # and a way to properly estimate
            txn.gas_limit *= 6 if txn.receiver == CONTRACT_DEPLOYER else 1
        else:
            txn.gas_limit = gas_limit

        assert txn.gas_limit not in ("auto", "max")
        # else: Assume user specified the correct amount or txn will fail and waste gas

        if txn.required_confirmations is None:
            txn.required_confirmations = self.network.required_confirmations
        elif not isinstance(txn.required_confirmations, int) or txn.required_confirmations < 0:
            raise TransactionError(message="'required_confirmations' must be a positive integer.")

        return txn
