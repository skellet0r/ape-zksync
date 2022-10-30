import hashlib
from typing import Any

from hexbytes import HexBytes


def hash_bytecode(bytecode: bytes) -> bytes:
    """zkSync deployment bytecode hash function.

    :param bytes bytecode: The contract deployment bytecode.
    :returns: The bytecode hash for use during contract creation.
    :rtype: bytes
    """
    bytecode_hash = hashlib.sha256(bytecode).digest()
    word_length = (len(bytecode) // 32).to_bytes(2, "big")
    return b"\x01\x00" + word_length + bytecode_hash[4:]


def to_bytes(value: Any, lstrip: bool = True) -> HexBytes:
    """Convert a value to bytes.

    :param value: A value to convert.
    :param bool lstrip: Remove leading null bytes from the output.
    :returns: A bytes value.
    :rtype: HexBytes
    """
    if not value:
        return HexBytes(b"")
    elif value and lstrip:
        return HexBytes(value).lstrip(b"\x00")
    else:
        return HexBytes(value)
