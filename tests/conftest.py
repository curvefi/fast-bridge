import boa
import pytest

CRVUSD_ADDRESS = '0xf939E0A03FB07F59A73314E73794Be0E57ac1b4E'
MINTER_ADDRESS = '0xC9332fdCB1C491Dcc683bAe86Fe3cb70360738BC'


@pytest.fixture()
def alice():
    return boa.env.generate_address()


@pytest.fixture()
def bob():
    return boa.env.generate_address()


@pytest.fixture()
def dev_deployer():
    return boa.env.generate_address()


@pytest.fixture()
def curve_dao():
    return boa.env.generate_address()


@pytest.fixture()
def emergency_dao():
    return boa.env.generate_address()



@pytest.fixture()
def lz_endpoint():
    return boa.load("tests/mocks/MockLZEndpoint.vy")


@pytest.fixture()
def vault_eid():
    return 1


@pytest.fixture()
def gas_limit():
    return 1000000


@pytest.fixture(scope="module")
def crvusd():
    return boa.load("tests/mocks/MockERC20.vy", override_address=CRVUSD_ADDRESS)


@pytest.fixture(scope="module")
def minter():
    return boa.load("tests/mocks/MockControllerFactory.vy", override_address=MINTER_ADDRESS)


@pytest.fixture()
def bridger():
    return boa.load("tests/mocks/MockBridger.vy")


@pytest.fixture()
def l2_messenger(dev_deployer, lz_endpoint, vault_eid, gas_limit):
    with boa.env.prank(dev_deployer):
        return boa.load("contracts/messengers/L2MessengerLZ.vy", lz_endpoint, vault_eid, gas_limit)


@pytest.fixture()
def vault_messenger(dev_deployer, lz_endpoint):
    with boa.env.prank(dev_deployer):
        return boa.load("contracts/messengers/VaultMessengerLZ.vy", lz_endpoint)


@pytest.fixture()
def fast_bridge_vault(dev_deployer, crvusd, minter, curve_dao, emergency_dao, vault_messenger):
    with boa.env.prank(dev_deployer):
        return boa.load("contracts/FastBridgeVault.vy", curve_dao, emergency_dao, [vault_messenger])


@pytest.fixture()
def fast_bridge_l2(dev_deployer, crvusd, fast_bridge_vault, bridger, l2_messenger):
    with boa.env.prank(dev_deployer):
        return boa.load("contracts/FastBridgeL2.vy", crvusd, fast_bridge_vault, bridger, l2_messenger)