import pytest
import boa


def test_set_fee_by_admin(fast_bridge_vault, curve_dao):
    new_fee = 10**16  # 1%
    
    with boa.env.prank(curve_dao):
        fast_bridge_vault.set_fee(new_fee)
    
    assert fast_bridge_vault.fee() == new_fee


def test_set_fee_max_value(fast_bridge_vault, curve_dao):
    max_fee = 10**18  # 100%
    
    with boa.env.prank(curve_dao):
        fast_bridge_vault.set_fee(max_fee)
    
    assert fast_bridge_vault.fee() == max_fee


def test_set_fee_too_high(fast_bridge_vault, curve_dao):
    too_high_fee = 10**18 + 1  # > 100%
    
    with boa.reverts():
        with boa.env.prank(curve_dao):
            fast_bridge_vault.set_fee(too_high_fee)


def test_set_fee_unauthorized(fast_bridge_vault, alice):
    with boa.reverts():
        with boa.env.prank(alice):
            fast_bridge_vault.set_fee(10**16)


def test_set_fee_zero(fast_bridge_vault, curve_dao):
    # First set a fee
    with boa.env.prank(curve_dao):
        fast_bridge_vault.set_fee(10**16)
    
    # Then set it back to zero
    with boa.env.prank(curve_dao):
        fast_bridge_vault.set_fee(0)
    
    assert fast_bridge_vault.fee() == 0