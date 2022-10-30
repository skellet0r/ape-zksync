from copy import deepcopy
from typing import Iterator

from ape.api import AccountAPI, ReceiptAPI, TransactionAPI
from ape.exceptions import AccountsError, SignatureError, TransactionError
from ape_accounts import AccountContainer, KeyfileAccount
from eth_account._utils.structured_data.hashing import hash_domain, hash_message
from eth_account.messages import SignableMessage

from ape_zksync.constants import ZKSYNC_TRANSACTION_STRUCT
from ape_zksync.transaction import LegacyTransaction, ZKSyncTransaction
from ape_zksync.utils import hash_bytecode


class ZKAccountContainer(AccountContainer):
    @property
    def accounts(self) -> Iterator[AccountAPI]:
        for keyfile in self._keyfiles:
            yield ZKSyncAccount(keyfile_path=keyfile)


class ZKSyncAccount(KeyfileAccount):
    def call(self, txn: TransactionAPI, send_everything: bool = False) -> ReceiptAPI:
        txn = self.prepare_transaction(txn)

        if send_everything:
            if txn.max_fee is None:
                raise TransactionError(message="Max fee must not be None.")
            if not txn.gas_limit or txn.gas_limit is None:
                raise TransactionError(message="The txn.gas_limit is not set.")
            txn.value = self.balance - (txn.max_fee * txn.gas_limit)
            if txn.value <= 0:
                raise AccountsError(
                    f"Sender does not have enough to cover transaction value and gas: "
                    f"{txn.max_fee * txn.gas_limit}"
                )

        if isinstance(txn, LegacyTransaction):
            txn.signature = self.sign_transaction(txn)
        elif isinstance(txn, ZKSyncTransaction):
            tx_struct = deepcopy(ZKSYNC_TRANSACTION_STRUCT)
            tx_struct["domain"]["chainId"] = txn.chain_id  # type: ignore
            tx_struct["message"] = dict(
                txType=txn.type,
                to=int(txn.receiver, 16),
                value=txn.value,
                data=txn.data,
                ergsLimit=txn.gas_limit,
                ergsPerPubdataByteLimit=txn.gas_per_pubdata_byte_limit,
                maxFeePerErg=txn.max_fee,
                maxPriorityFeePerErg=txn.max_priority_fee,
                nonce=txn.nonce,
                paymaster=int(txn.paymaster or "0x0", 16),
                factoryDeps=[hash_bytecode(v) for v in txn.factory_deps],
                paymasterInput=txn.paymaster_input or b"",
            )
            tx_struct["message"]["from"] = int(txn.sender, 16)  # type: ignore
            signable_message = SignableMessage(
                b"\x01",
                hash_domain(tx_struct),
                hash_message(tx_struct),
            )

            txn.signature = self.sign_message(signable_message)

        if not txn.signature:
            raise SignatureError("The transaction was not signed.")

        return self.provider.send_transaction(txn)
