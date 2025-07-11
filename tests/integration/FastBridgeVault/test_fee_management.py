"""Integration tests for FastBridgeVault fee management functions."""

import boa
from conftest import EMPTY_ADDRESS


def test_set_fee_basic(forked_env, fast_bridge_vault, curve_dao):
    """Test basic set_fee functionality."""
    # Check initial fee
    assert fast_bridge_vault.fee() == 0
    
    # Set new fee (0.5%)
    new_fee = 5 * 10**15  # 0.005 * 10**18
    with boa.env.prank(curve_dao):
        fast_bridge_vault.set_fee(new_fee)
    
    # Verify change
    assert fast_bridge_vault.fee() == new_fee


def test_set_fee_max_limit(forked_env, fast_bridge_vault, curve_dao):
    """Test set_fee respects maximum limit."""
    # Try to set fee above 100%
    with boa.env.prank(curve_dao):
        with boa.reverts():
            fast_bridge_vault.set_fee(11 * 10**17)  # 110%
    
    # Set exactly 100% - should work
    with boa.env.prank(curve_dao):
        fast_bridge_vault.set_fee(10**18)
    
    assert fast_bridge_vault.fee() == 10**18


def test_set_fee_unauthorized(forked_env, fast_bridge_vault):
    """Test set_fee fails for unauthorized caller."""
    unauthorized = boa.env.generate_address()
    
    with boa.env.prank(unauthorized):
        with boa.reverts("access_control: account is missing role"):
            fast_bridge_vault.set_fee(10**16)  # 0.01 * 10**18


def test_set_fee_receiver_basic(forked_env, fast_bridge_vault, curve_dao):
    """Test basic set_fee_receiver functionality."""
    # Check initial fee receiver
    initial_receiver = fast_bridge_vault.fee_receiver()
    assert initial_receiver == "0xa2Bcd1a4Efbd04B63cd03f5aFf2561106ebCCE00"  # FeeCollector
    
    # Set new fee receiver
    new_receiver = boa.env.generate_address()
    with boa.env.prank(curve_dao):
        fast_bridge_vault.set_fee_receiver(new_receiver)
    
    # Verify change
    assert fast_bridge_vault.fee_receiver() == new_receiver


def test_set_fee_receiver_empty_address(forked_env, fast_bridge_vault, curve_dao):
    """Test set_fee_receiver rejects empty address."""
    with boa.env.prank(curve_dao):
        with boa.reverts():
            fast_bridge_vault.set_fee_receiver(EMPTY_ADDRESS)


def test_set_fee_receiver_unauthorized(forked_env, fast_bridge_vault):
    """Test set_fee_receiver fails for unauthorized caller."""
    unauthorized = boa.env.generate_address()
    new_receiver = boa.env.generate_address()
    
    with boa.env.prank(unauthorized):
        with boa.reverts("access_control: account is missing role"):
            fast_bridge_vault.set_fee_receiver(new_receiver)


def test_fee_collection_integration(forked_env, fast_bridge_vault, vault_messenger, curve_dao, crvusd):
    """Test fee collection with mint operation."""
    # Set 2% fee
    fee_rate = 2 * 10**16  # 0.02 * 10**18
    new_fee_receiver = boa.env.generate_address()
    
    with boa.env.prank(curve_dao):
        fast_bridge_vault.set_fee(fee_rate)
        fast_bridge_vault.set_fee_receiver(new_fee_receiver)
    
    # Fund the vault
    boa.deal(crvusd, fast_bridge_vault.address, 10000 * 10**18)
    
    # Mint with fee
    receiver = boa.env.generate_address()
    mint_amount = 1000 * 10**18
    
    initial_fee_balance = fast_bridge_vault.balanceOf(new_fee_receiver)
    
    with boa.env.prank(vault_messenger.address):
        minted = fast_bridge_vault.mint(receiver, mint_amount)
    
    # Calculate expected values
    expected_fee = mint_amount * fee_rate // 10**18
    expected_received = mint_amount - expected_fee
    
    # Verify fee collection
    assert minted == expected_received
    assert crvusd.balanceOf(receiver) == expected_received
    assert fast_bridge_vault.balanceOf(new_fee_receiver) == initial_fee_balance + expected_fee
    
    # Fee receiver can claim their balance
    with boa.env.prank(boa.env.generate_address()):  # Anyone can trigger mint for fee receiver
        fee_minted = fast_bridge_vault.mint(new_fee_receiver, 0)
    
    assert fee_minted == expected_fee
    assert crvusd.balanceOf(new_fee_receiver) == expected_fee
    assert fast_bridge_vault.balanceOf(new_fee_receiver) == 0


def test_fee_changes_during_operations(forked_env, fast_bridge_vault, vault_messenger, curve_dao, crvusd):
    """Test changing fees during operations."""
    # Fund the vault
    boa.deal(crvusd, fast_bridge_vault.address, 10000 * 10**18)
    
    receiver = boa.env.generate_address()
    fee_receiver = fast_bridge_vault.fee_receiver()
    
    # First mint with 0% fee
    with boa.env.prank(vault_messenger.address):
        minted1 = fast_bridge_vault.mint(receiver, 1000 * 10**18)
    assert minted1 == 1000 * 10**18
    
    # Set 1% fee
    with boa.env.prank(curve_dao):
        fast_bridge_vault.set_fee(10**16)  # 0.01 * 10**18
    
    # Second mint with 1% fee
    with boa.env.prank(vault_messenger.address):
        minted2 = fast_bridge_vault.mint(receiver, 1000 * 10**18)
    assert minted2 == 990 * 10**18  # 1% fee deducted
    
    # Verify fee was collected
    assert fast_bridge_vault.balanceOf(fee_receiver) == 10 * 10**18