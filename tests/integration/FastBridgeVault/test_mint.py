"""Integration tests for FastBridgeVault mint function."""

import boa


def test_mint_as_minter(forked_env, fast_bridge_vault, vault_messenger, crvusd, dev_deployer):
    """Test mint functionality when called by authorized minter."""
    receiver = boa.env.generate_address()
    mint_amount = 1000 * 10**18
    
    # Fund the vault with crvUSD (simulating bridged funds)
    boa.deal(crvusd, fast_bridge_vault.address, mint_amount * 2)
    
    # Check initial balances
    assert fast_bridge_vault.balanceOf(receiver) == 0
    initial_vault_balance = crvusd.balanceOf(fast_bridge_vault.address)
    
    # Mint as authorized minter (vault_messenger)
    with boa.env.prank(vault_messenger.address):
        minted = fast_bridge_vault.mint(receiver, mint_amount)
    
    # Verify mint occurred
    assert minted == mint_amount
    assert crvusd.balanceOf(receiver) == mint_amount
    assert crvusd.balanceOf(fast_bridge_vault.address) == initial_vault_balance - mint_amount
    assert fast_bridge_vault.balanceOf(receiver) == 0  # Should be 0 after successful mint


def test_mint_with_fee(forked_env, fast_bridge_vault, vault_messenger, crvusd, dev_deployer, curve_dao):
    """Test mint with fee deduction."""
    # Set a 1% fee
    fee = 10**16  # 0.01 * 10**18 = 1%
    with boa.env.prank(curve_dao):
        fast_bridge_vault.set_fee(fee)
    
    receiver = boa.env.generate_address()
    mint_amount = 1000 * 10**18
    
    # Fund the vault
    boa.deal(crvusd, fast_bridge_vault.address, mint_amount * 2)
    
    fee_receiver = fast_bridge_vault.fee_receiver()
    initial_fee_balance = fast_bridge_vault.balanceOf(fee_receiver)
    
    # Mint as authorized minter
    with boa.env.prank(vault_messenger.address):
        minted = fast_bridge_vault.mint(receiver, mint_amount)
    
    # Calculate expected values
    expected_fee = mint_amount * fee // 10**18
    expected_received = mint_amount - expected_fee
    
    # Verify mint with fee
    assert minted == expected_received
    assert crvusd.balanceOf(receiver) == expected_received
    assert fast_bridge_vault.balanceOf(fee_receiver) == initial_fee_balance + expected_fee


def test_mint_insufficient_balance(forked_env, fast_bridge_vault, vault_messenger, crvusd):
    """Test mint when vault has insufficient balance."""
    receiver = boa.env.generate_address()
    mint_amount = 1000 * 10**18
    
    # Fund with less than requested
    boa.deal(crvusd, fast_bridge_vault.address, 500 * 10**18)  # Only half
    
    # Mint as authorized minter
    with boa.env.prank(vault_messenger.address):
        minted = fast_bridge_vault.mint(receiver, mint_amount)
    
    # Should mint what's available and store the rest as balance
    assert minted == 500 * 10**18
    assert crvusd.balanceOf(receiver) == 500 * 10**18
    assert fast_bridge_vault.balanceOf(receiver) == 500 * 10**18  # Remaining balance


def test_mint_non_minter(forked_env, fast_bridge_vault, crvusd, vault_messenger):
    """Test mint when called by non-minter."""
    receiver = boa.env.generate_address()
    non_minter = boa.env.generate_address()
    
    # Fund the vault
    boa.deal(crvusd, fast_bridge_vault.address, 1000 * 10**18)
    
    # Set a balance for the receiver through a minter
    with boa.env.prank(vault_messenger.address):
        # First create a situation where receiver has balance
        # This happens when there's insufficient vault balance
        boa.deal(crvusd, fast_bridge_vault.address, 0)  # Empty the vault first
        fast_bridge_vault.mint(receiver, 100 * 10**18)  # This creates balance
    
    # Refund the vault
    boa.deal(crvusd, fast_bridge_vault.address, 1000 * 10**18)
    
    # Try to mint as non-minter (amount parameter should be ignored)
    with boa.env.prank(non_minter):
        minted = fast_bridge_vault.mint(receiver, 500 * 10**18)
    
    # Should only mint the existing balance, not the requested amount
    assert minted == 100 * 10**18
    assert crvusd.balanceOf(receiver) == 100 * 10**18
    assert fast_bridge_vault.balanceOf(receiver) == 0


def test_mint_when_killed(forked_env, fast_bridge_vault, vault_messenger, emergency_dao, crvusd):
    """Test mint fails when contract or minter is killed."""
    receiver = boa.env.generate_address()
    mint_amount = 1000 * 10**18
    
    # Fund the vault
    boa.deal(crvusd, fast_bridge_vault.address, mint_amount)
    
    # Kill all minting
    with boa.env.prank(emergency_dao):
        fast_bridge_vault.set_killed(True)  # Kill all
    
    # Try to mint
    with boa.env.prank(vault_messenger.address):
        with boa.reverts():
            fast_bridge_vault.mint(receiver, mint_amount)
    
    # Unkill all, but kill specific minter
    with boa.env.prank(emergency_dao):
        fast_bridge_vault.set_killed(False)
        fast_bridge_vault.set_killed(True, vault_messenger.address)
    
    # Try to mint again
    with boa.env.prank(vault_messenger.address):
        with boa.reverts():
            fast_bridge_vault.mint(receiver, mint_amount)


def test_mint_with_rug_scheduled(forked_env, fast_bridge_vault, vault_messenger, crvusd, dev_deployer):
    """Test mint behavior when rug is scheduled."""
    receiver = boa.env.generate_address()
    mint_amount = 1000 * 10**18
    
    # Fund the vault
    boa.deal(crvusd, fast_bridge_vault.address, mint_amount * 2)
    
    # Schedule a rug (this might not actually be needed in test environment)
    fast_bridge_vault.schedule_rug()
    
    # Mint should still work, but might trigger rug_debt_ceiling call
    with boa.env.prank(vault_messenger.address):
        minted = fast_bridge_vault.mint(receiver, mint_amount)
    
    # Verify mint occurred (exact behavior depends on MINTER contract state)
    assert minted <= mint_amount
    assert crvusd.balanceOf(receiver) == minted


def test_mint_multiple_receivers(forked_env, fast_bridge_vault, vault_messenger, crvusd):
    """Test minting to multiple receivers."""
    receivers = [boa.env.generate_address() for _ in range(3)]
    amounts = [100 * 10**18, 200 * 10**18, 300 * 10**18]
    
    # Fund the vault
    total_amount = sum(amounts)
    boa.deal(crvusd, fast_bridge_vault.address, total_amount * 2)
    
    # Mint to each receiver
    for receiver, amount in zip(receivers, amounts):
        with boa.env.prank(vault_messenger.address):
            minted = fast_bridge_vault.mint(receiver, amount)
        
        assert minted == amount
        assert crvusd.balanceOf(receiver) == amount


def test_mint_partial_then_complete(forked_env, fast_bridge_vault, vault_messenger, crvusd):
    """Test partial mint followed by completion when funds arrive."""
    receiver = boa.env.generate_address()
    mint_amount = 1000 * 10**18
    
    # Fund with partial amount
    boa.deal(crvusd, fast_bridge_vault.address, 400 * 10**18)
    
    # First mint - partial
    with boa.env.prank(vault_messenger.address):
        minted1 = fast_bridge_vault.mint(receiver, mint_amount)
    
    assert minted1 == 400 * 10**18
    assert fast_bridge_vault.balanceOf(receiver) == 600 * 10**18  # Remaining
    
    # Fund the rest
    boa.deal(crvusd, fast_bridge_vault.address, 700 * 10**18)
    
    # Second mint - complete the rest as a minter
    with boa.env.prank(vault_messenger.address):
        minted2 = fast_bridge_vault.mint(receiver, 0)  # Amount doesn't matter for already recorded balance
    
    assert minted2 == 600 * 10**18
    assert fast_bridge_vault.balanceOf(receiver) == 0
    assert crvusd.balanceOf(receiver) == 1000 * 10**18  # Total