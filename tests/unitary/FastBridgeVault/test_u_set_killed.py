import pytest
import boa


def test_set_killed_all(fast_bridge_vault, emergency_dao, alice):
    # Emergency DAO can kill all
    with boa.env.prank(emergency_dao):
        fast_bridge_vault.set_killed(True)
    
    assert fast_bridge_vault.is_killed("0x0000000000000000000000000000000000000000") == True
    
    # Can unkill
    with boa.env.prank(emergency_dao):
        fast_bridge_vault.set_killed(False)
    
    assert fast_bridge_vault.is_killed("0x0000000000000000000000000000000000000000") == False


def test_set_killed_specific_address(fast_bridge_vault, emergency_dao, alice):
    # Kill specific address
    with boa.env.prank(emergency_dao):
        fast_bridge_vault.set_killed(True, alice)
    
    assert fast_bridge_vault.is_killed(alice) == True
    assert fast_bridge_vault.is_killed("0x0000000000000000000000000000000000000000") == False
    
    # Unkill specific address
    with boa.env.prank(emergency_dao):
        fast_bridge_vault.set_killed(False, alice)
    
    assert fast_bridge_vault.is_killed(alice) == False


def test_set_killed_unauthorized(fast_bridge_vault, alice):
    # Non-emergency DAO cannot kill
    with boa.reverts():
        with boa.env.prank(alice):
            fast_bridge_vault.set_killed(True)


def test_set_killed_admin_cannot_kill(fast_bridge_vault, curve_dao):
    # Even admin cannot kill (only emergency DAO)
    with boa.reverts():
        with boa.env.prank(curve_dao):
            fast_bridge_vault.set_killed(True)