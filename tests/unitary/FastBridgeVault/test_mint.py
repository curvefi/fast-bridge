import pytest
import boa
from boa import env


def test_mint_as_minter(fast_bridge_vault, crvusd, vault_messenger, alice):
    # Setup: Give vault some crvUSD
    amount = 10**20  # 100 crvUSD
    boa.deal(crvusd, fast_bridge_vault.address, amount)
    
    # Mint as minter
    with boa.env.prank(vault_messenger.address):
        result = fast_bridge_vault.mint(alice, amount)
    
    assert result == amount
    assert crvusd.balanceOf(alice) == amount
    assert fast_bridge_vault.balanceOf(alice) == 0


def test_mint_as_non_minter(fast_bridge_vault, crvusd, alice, bob, vault_messenger):
    # Test that non-minters can claim their existing balance
    amount = 10**20
    
    # First, set a balance for alice without having crvUSD in vault
    # This simulates a scenario where balance was set but tokens not yet available
    with boa.env.prank(vault_messenger.address):
        fast_bridge_vault.mint(alice, amount)
    
    # Alice should have a balance recorded
    assert fast_bridge_vault.balanceOf(alice) == amount
    
    # Now add crvUSD to vault
    boa.deal(crvusd, fast_bridge_vault.address, amount)
    
    # Non-minter (bob) can trigger alice's mint with amount=0
    with boa.env.prank(bob):
        result = fast_bridge_vault.mint(alice, 0)
    
    assert result == amount
    assert crvusd.balanceOf(alice) == amount
    assert fast_bridge_vault.balanceOf(alice) == 0


def test_mint_with_fee(fast_bridge_vault, crvusd, vault_messenger, curve_dao, alice):
    # Set fee to 1%
    fee = 10**16  # 0.01 * 10**18
    with boa.env.prank(curve_dao):
        fast_bridge_vault.set_fee(fee)
    
    # Setup: Give vault some crvUSD
    amount = 10**20  # 100 crvUSD
    boa.deal(crvusd, fast_bridge_vault.address, amount)
    
    fee_receiver = fast_bridge_vault.fee_receiver()
    
    # Mint as minter with fee
    with boa.env.prank(vault_messenger.address):
        result = fast_bridge_vault.mint(alice, amount)
    
    expected_fee = amount * fee // 10**18
    expected_amount = amount - expected_fee
    
    assert result == expected_amount
    assert crvusd.balanceOf(alice) == expected_amount
    assert fast_bridge_vault.balanceOf(alice) == 0
    assert fast_bridge_vault.balanceOf(fee_receiver) == expected_fee


def test_mint_when_killed(fast_bridge_vault, crvusd, vault_messenger, emergency_dao, alice):
    # Kill the vault
    with boa.env.prank(emergency_dao):
        fast_bridge_vault.set_killed(True)
    
    # Try to mint - should revert
    with boa.reverts():
        with boa.env.prank(vault_messenger.address):
            fast_bridge_vault.mint(alice, 10**18)


def test_mint_when_killed_specific_minter(fast_bridge_vault, crvusd, vault_messenger, emergency_dao, alice):
    # Kill specific minter
    with boa.env.prank(emergency_dao):
        fast_bridge_vault.set_killed(True, vault_messenger.address)
    
    # Try to mint - should revert
    with boa.reverts():
        with boa.env.prank(vault_messenger.address):
            fast_bridge_vault.mint(alice, 10**18)


def test_mint_partial_balance(fast_bridge_vault, crvusd, vault_messenger, alice):
    # Setup: Give vault less crvUSD than requested
    vault_amount = 10**19  # 10 crvUSD
    requested_amount = 10**20  # 100 crvUSD
    
    boa.deal(crvusd, fast_bridge_vault.address, vault_amount)
    
    # Mint more than available
    with boa.env.prank(vault_messenger.address):
        result = fast_bridge_vault.mint(alice, requested_amount)
    
    assert result == vault_amount
    assert crvusd.balanceOf(alice) == vault_amount
    assert fast_bridge_vault.balanceOf(alice) == requested_amount - vault_amount