import boa
import pytest
import os
import json
from eth_utils import to_bytes

boa.set_etherscan(api_key=os.getenv("ETHERSCAN_API_KEY"))


BOA_CACHE = True

LZ_ENDPOINT = "0x1a44076050125825900e736c501f859c50fE728c"  # mainnet
LZ_EID = 30101  # Ethereum mainnet
EMPTY_ADDRESS = boa.eval("empty(address)")
def to_bytes32(value):
    """Convert a string or address to bytes32 format."""
    if isinstance(value, str) and value.startswith("0x"):
        # Convert hex string to bytes and pad to 32 bytes
        return to_bytes(hexstr=value).rjust(32, b"\x00")
    else:
        # For non-hex strings or other types
        return to_bytes(text=str(value)).rjust(32, b"\x00")


@pytest.fixture(scope="session")
def drpc_api_key():
    return os.getenv("DRPC_API_KEY")


@pytest.fixture(scope="function")
def rpc_url(drpc_api_key):
    """Fixture to generate the correct RPC URL for each chain."""
    return 'https://lb.drpc.org/ogrpc?network=ethereum&dkey=' + drpc_api_key


@pytest.fixture()
def forked_env(rpc_url):
    """Automatically fork each test with the specified chain."""
    block_to_fork = "latest"
    with boa.swap_env(boa.Env()):
        if BOA_CACHE:
            boa.fork(url=rpc_url, block_identifier=block_to_fork)
        else:
            boa.fork(url=rpc_url, block_identifier=block_to_fork, cache_dir=None)
        boa.env.enable_fast_mode()
        yield



@pytest.fixture()
def l2_messenger(dev_deployer):
    with boa.env.prank(dev_deployer):
        messenger = boa.load("contracts/messengers/L2MessengerLZ.vy", LZ_ENDPOINT, LZ_EID, 100_000)
        # Set a peer to make quote_message_fee work
        test_peer = to_bytes32("0x" + "42" * 20)  # Dummy peer for testing
        messenger.setPeer(LZ_EID, test_peer)
        return messenger


@pytest.fixture()
def vault_messenger(dev_deployer):
    with boa.env.prank(dev_deployer):
        return boa.load("contracts/messengers/VaultMessengerLZ.vy", LZ_ENDPOINT)


@pytest.fixture()
def fast_bridge_vault(dev_deployer, curve_dao, emergency_dao, vault_messenger):
    with boa.env.prank(dev_deployer):
        return boa.load("contracts/FastBridgeVault.vy", curve_dao, emergency_dao, [vault_messenger])


@pytest.fixture()
def fast_bridge_l2(dev_deployer, crvusd, fast_bridge_vault, bridger, l2_messenger):
    with boa.env.prank(dev_deployer):
        fast_bridge_l2 = boa.load("contracts/FastBridgeL2.vy", crvusd, fast_bridge_vault, bridger, l2_messenger)
        l2_messenger.set_fast_bridge_l2(fast_bridge_l2.address)
        return fast_bridge_l2
    

@pytest.fixture()
def crvusd():
    return boa.from_etherscan("0xf939E0A03FB07F59A73314E73794Be0E57ac1b4E")


@pytest.fixture()
def dev_deployer():
    """Developer deployer account."""
    return boa.env.generate_address()


@pytest.fixture()
def curve_dao():
    """Curve DAO address for admin functions."""
    return boa.env.generate_address()


@pytest.fixture()
def emergency_dao():
    """Emergency DAO address for kill functions."""
    return boa.env.generate_address()


@pytest.fixture()
def bridger(dev_deployer):
    """Mock bridger contract."""
    with boa.env.prank(dev_deployer):
        return boa.load("tests/mocks/MockBridger.vy")