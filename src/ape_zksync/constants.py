from ape.types import AddressType
from ethpm_types import ContractType

from ape_zksync.data import loads

ETH_TOKEN: AddressType = "0x000000000000000000000000000000000000800A"
CONTRACT_DEPLOYER: AddressType = "0x0000000000000000000000000000000000008006"

MAX_BYTECODE_SIZE = (2**16 - 1) * 32

ERC20_TYPE = ContractType.parse_raw(loads("ERC20.json"))
CONTRACT_DEPLOYER_TYPE = ContractType.parse_raw(loads("ContractDeployer.json"))

DEFAULT_GAS_PER_PUBDATA_BYTE_LIMIT = 160_000
