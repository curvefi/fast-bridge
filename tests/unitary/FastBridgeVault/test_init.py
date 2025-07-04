import pytest
import boa
from boa import env


def test_default_behavior(fast_bridge_vault, crvusd, minter, curve_dao, emergency_dao, vault_messenger):
    assert fast_bridge_vault.CRVUSD() == crvusd.address
    assert fast_bridge_vault.MINTER() == minter.address
    assert fast_bridge_vault.fee() == 0
    assert fast_bridge_vault.fee_receiver() == "0xa2Bcd1a4Efbd04B63cd03f5aFf2561106ebCCE00"
    assert fast_bridge_vault.rug_scheduled() == False
    
    # Check roles
    assert fast_bridge_vault.hasRole(fast_bridge_vault.DEFAULT_ADMIN_ROLE(), curve_dao) == True
    assert fast_bridge_vault.hasRole(fast_bridge_vault.MINTER_ROLE(), vault_messenger.address) == True
    assert fast_bridge_vault.hasRole(fast_bridge_vault.KILLER_ROLE(), emergency_dao) == True
    
    # Check CRVUSD approval to MINTER
    assert crvusd.allowance(fast_bridge_vault.address, minter.address) == 2**256 - 1


def test_multiple_minters(dev_deployer, crvusd, minter, curve_dao, emergency_dao):
    minter1 = env.generate_address()
    minter2 = env.generate_address()
    minter3 = env.generate_address()
    
    with boa.env.prank(dev_deployer):
        vault = boa.load("contracts/FastBridgeVault.vy", curve_dao, emergency_dao, [minter1, minter2, minter3])
    
    assert vault.hasRole(vault.MINTER_ROLE(), minter1) == True
    assert vault.hasRole(vault.MINTER_ROLE(), minter2) == True
    assert vault.hasRole(vault.MINTER_ROLE(), minter3) == True