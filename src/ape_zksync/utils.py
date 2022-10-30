import hashlib


def hash_bytecode(bytecode: bytes) -> bytes:
    """zkSync deployment bytecode hash function.

    :param bytes bytecode: The contract deployment bytecode.
    :returns: The bytecode hash for use during contract creation.
    :rtype: bytes
    """
    bytecode_hash = hashlib.sha256(bytecode).digest()
    word_length = (len(bytecode) // 32).to_bytes(2, "big")
    return b"\x01\x00" + word_length + bytecode_hash[4:]
