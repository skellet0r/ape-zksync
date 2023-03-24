from ape.types import AddressType
from ethpm_types import ContractType

from ape_zksync.data import loads

ETH_TOKEN: AddressType = "0x000000000000000000000000000000000000800A"
CONTRACT_DEPLOYER: AddressType = "0x0000000000000000000000000000000000008006"

MAX_BYTECODE_SIZE = (2**16 - 1) * 32

ERC20_TYPE = ContractType.parse_raw(loads("ERC20.json"))
CONTRACT_DEPLOYER_TYPE = ContractType.parse_raw(loads("ContractDeployer.json"))

DEFAULT_GAS_PER_PUBDATA_BYTE_LIMIT = 160_000

ZKSYNC_TRANSACTION_STRUCT = {
    "types": {
        "EIP712Domain": [
            {"name": "name", "type": "string"},
            {"name": "version", "type": "string"},
            {"name": "chainId", "type": "uint256"},
        ],
        "Transaction": [
            {"name": "txType", "type": "uint256"},
            {"name": "from", "type": "uint256"},
            {"name": "to", "type": "uint256"},
            {"name": "gasLimit", "type": "uint256"},
            {"name": "gasPerPubdataByteLimit", "type": "uint256"},
            {"name": "maxFeePerGas", "type": "uint256"},
            {"name": "maxPriorityFeePerGas", "type": "uint256"},
            {"name": "paymaster", "type": "uint256"},
            {"name": "nonce", "type": "uint256"},
            {"name": "value", "type": "uint256"},
            {"name": "data", "type": "bytes"},
            {"name": "factoryDeps", "type": "bytes32[]"},
            {"name": "paymasterInput", "type": "bytes"},
        ],
    },
    "primaryType": "Transaction",
    "domain": {
        "name": "zkSync",
        "version": "2",
    },
}
