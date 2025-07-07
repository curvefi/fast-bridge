import boa
import pytest
import os
import json

BOA_CACHE = False

LZ_ENDPOINT = "0x1a44076050125825900e736c501f859c50fE728c"  # mainnet
LZ_EID = 30101  # Ethereum mainnet
EMPTY_ADDRESS = boa.eval("empty(address)")


@pytest.fixture(scope="session")
def chains():
    with open("chains.json", "r") as file:
        return json.load(file)


@pytest.fixture(scope="session")
def drpc_api_key():
    return os.getenv("DRPC_API_KEY")


@pytest.fixture(scope="function")
def rpc_url(chains, chain_name, drpc_api_key):
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
        return boa.load("contracts/messengers/L2MessengerLZ.vy", LZ_ENDPOINT, LZ_EID, 100_000)


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
        return boa.load("contracts/FastBridgeL2.vy", crvusd, fast_bridge_vault, bridger, l2_messenger)