from typing import Iterator, Optional

import click
from ape.api import AccountAPI, TransactionAPI
from ape.exceptions import AccountsError
from ape.types import TransactionSignature
from ape_accounts import AccountContainer, KeyfileAccount
from ape_ethereum.transactions import StaticFeeTransaction
from eip712.messages import EIP712Message
from eth_account import Account as EthAccount
from eth_utils import to_bytes
from hexbytes import HexBytes

from ape_zksync.ecosystems import ZKSyncTransaction


class Transaction(EIP712Message):
    _name_: "string" = "zkSync"  # type: ignore  # noqa: F821
    _version_: "string" = "2"  # type: ignore  # noqa: F821
    _chainId_: "uint256"  # type: ignore  # noqa: F821

    txType: "uint8"  # type: ignore  # noqa: F821
    to: "uint256"  # type: ignore  # noqa: F821
    value: "uint256"  # type: ignore  # noqa: F821
    data: "bytes"  # type: ignore  # noqa: F821
    feeToken: "uint256"  # type: ignore  # noqa: F821
    ergsLimit: "uint256"  # type: ignore  # noqa: F821
    ergsPerPubdataByteLimit: "uint256"  # type: ignore  # noqa: F821
    ergsPrice: "uint256"  # type: ignore  # noqa: F821
    nonce: "uint256"  # type: ignore  # noqa: F821


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
            tx_struct = Transaction(
                _chainId_=txn.chain_id,
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
            return self.sign_message(tx_struct)
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
