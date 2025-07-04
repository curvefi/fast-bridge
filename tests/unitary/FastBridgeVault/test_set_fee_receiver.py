import pytest
import boa
from boa import env


def test_set_fee_receiver_by_admin(fast_bridge_vault, curve_dao):
    new_receiver = env.generate_address()
    
    with boa.env.prank(curve_dao):
        fast_bridge_vault.set_fee_receiver(new_receiver)
    
    assert fast_bridge_vault.fee_receiver() == new_receiver


def test_set_fee_receiver_empty_address(fast_bridge_vault, curve_dao):
    # Cannot set empty address
    with boa.reverts():
        with boa.env.prank(curve_dao):
            fast_bridge_vault.set_fee_receiver("0x0000000000000000000000000000000000000000")


def test_set_fee_receiver_unauthorized(fast_bridge_vault, alice):
    new_receiver = env.generate_address()
    
    with boa.reverts():
        with boa.env.prank(alice):
            fast_bridge_vault.set_fee_receiver(new_receiver)


def test_fee_receiver_gets_fees(fast_bridge_vault, crvusd, vault_messenger, curve_dao, alice):
    # Set new fee receiver
    new_receiver = env.generate_address()
    with boa.env.prank(curve_dao):
        fast_bridge_vault.set_fee_receiver(new_receiver)
        fast_bridge_vault.set_fee(10**16)  # 1% fee
    
    # Setup: Give vault some crvUSD
    amount = 10**20  # 100 crvUSD
    boa.deal(crvusd, fast_bridge_vault.address, amount)
    
    # Mint with fee
    with boa.env.prank(vault_messenger.address):
        fast_bridge_vault.mint(alice, amount)
    
    expected_fee = amount * 10**16 // 10**18
    assert fast_bridge_vault.balanceOf(new_receiver) == expected_fee