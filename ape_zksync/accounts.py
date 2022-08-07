from copy import deepcopy
from typing import Iterator, Optional

import click
from ape.api import AccountAPI, TransactionAPI
from ape.exceptions import AccountsError
from ape.types import TransactionSignature
from ape_accounts import AccountContainer, KeyfileAccount
from ape_ethereum.transactions import StaticFeeTransaction
from eth_account import Account as EthAccount
from eth_account._utils.structured_data.hashing import hash_domain
from eth_account._utils.structured_data.hashing import (
    hash_message as hash_eip712_message,
)
from eth_account.messages import SignableMessage
from eth_utils import to_bytes
from hexbytes import HexBytes

from ape_zksync.ecosystems import ZKSyncTransaction

STRUCT = {
    "types": {
        "EIP712Domain": [
            {"name": "name", "type": "string"},
            {"name": "version", "type": "string"},
            {"name": "chainId", "type": "uint256"},
        ],
        "Transaction": [
            {"name": "txType", "type": "uint8"},
            {"name": "to", "type": "uint256"},
            {"name": "value", "type": "uint256"},
            {"name": "data", "type": "bytes"},
            {"name": "feeToken", "type": "uint256"},
            {"name": "ergsLimit", "type": "uint256"},
            {"name": "ergsPerPubdataByteLimit", "type": "uint256"},
            {"name": "ergsPrice", "type": "uint256"},
            {"name": "nonce", "type": "uint256"},
        ],
    },
    "primaryType": "Transaction",
    "domain": {
        "name": "zkSync",
        "version": "2",
    },
}


class ZKAccountContainer(AccountContainer):
    @property
    def accounts(self) -> Iterator[AccountAPI]:
        for keyfile in self._keyfiles:
            yield ZKSyncAccount(keyfile_path=keyfile)


class ZKSyncAccount(KeyfileAccount):
    __autosign: bool = False
    __cached_key: Optional[HexBytes] = None

    def sign_transaction(self, txn: TransactionAPI) -> Optional[TransactionSignature]:
        user_approves = self.__autosign or click.confirm(f"{txn}\n\nSign: ")
        if not user_approves:
            return None

        if isinstance(txn, ZKSyncTransaction):
            tx_struct = deepcopy(STRUCT)
            tx_struct["domain"]["chainId"] = txn.chain_id  # type: ignore
            tx_struct["message"] = dict(
                txType=txn.type,
                to=int(txn.receiver, 16),
                value=txn.value,
                data=txn.data,
                feeToken=int(txn.fee_token, 16),
                ergsLimit=txn.gas_limit,
                ergsPerPubdataByteLimit=txn.ergs_per_pub_data,
                ergsPrice=txn.gas_price,
                nonce=txn.nonce,
            )
            signable_message = SignableMessage(
                HexBytes(b"\x01"),
                hash_domain(tx_struct),
                hash_eip712_message(tx_struct),
            )

            return self.sign_message(signable_message)
        elif isinstance(txn, StaticFeeTransaction):
            signed_txn = EthAccount.sign_transaction(
                txn.dict(exclude_none=True, by_alias=True), self.__key
            )
            return TransactionSignature(  # type: ignore
                v=signed_txn.v,
                r=to_bytes(signed_txn.r),
                s=to_bytes(signed_txn.s),
            )

        raise AccountsError(f"Invalid tx type: {txn.type}")
