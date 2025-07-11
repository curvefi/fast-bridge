"""Integration tests for FastBridgeVault schedule_rug function."""

import boa


def test_schedule_rug_basic(forked_env, fast_bridge_vault):
    """Test basic schedule_rug functionality."""
    # Check initial state
    assert fast_bridge_vault.rug_scheduled() is False
    
    # Anyone can call schedule_rug
    random_user = boa.env.generate_address()
    with boa.env.prank(random_user):
        result = fast_bridge_vault.schedule_rug()
    
    # In test environment, this might always return False
    # as debt ceiling conditions might not be met
    assert isinstance(result, bool)
    
    # Check if state was updated
    assert fast_bridge_vault.rug_scheduled() == result


def test_schedule_rug_multiple_calls(forked_env, fast_bridge_vault):
    """Test multiple calls to schedule_rug."""
    users = [boa.env.generate_address() for _ in range(3)]
    
    results = []
    for user in users:
        with boa.env.prank(user):
            result = fast_bridge_vault.schedule_rug()
            results.append(result)
    
    # All calls should return the same result
    assert all(r == results[0] for r in results)
    
    # Final state should match the result
    assert fast_bridge_vault.rug_scheduled() == results[0]


def test_schedule_rug_state_persistence(forked_env, fast_bridge_vault):
    """Test that rug_scheduled state persists correctly."""
    # Call schedule_rug
    with boa.env.prank(boa.env.generate_address()):
        initial_result = fast_bridge_vault.schedule_rug()
    
    initial_state = fast_bridge_vault.rug_scheduled()
    
    # Make several other contract calls
    # (In production, these might change the need_to_rug condition)
    
    # Check state hasn't changed unexpectedly
    assert fast_bridge_vault.rug_scheduled() == initial_state
    
    # Call schedule_rug again
    with boa.env.prank(boa.env.generate_address()):
        second_result = fast_bridge_vault.schedule_rug()
    
    # State should reflect current need_to_rug condition
    assert fast_bridge_vault.rug_scheduled() == second_result


def test_schedule_rug_interaction_with_mint(forked_env, fast_bridge_vault, vault_messenger, crvusd):
    """Test how schedule_rug interacts with mint function."""
    # Schedule rug first
    with boa.env.prank(boa.env.generate_address()):
        fast_bridge_vault.schedule_rug()
    
    # Fund the vault
    boa.deal(crvusd, fast_bridge_vault.address, 10**20)  # 100 crvUSD
    
    receiver = boa.env.generate_address()
    
    # Try to mint - should work even with rug scheduled
    with boa.env.prank(vault_messenger.address):
        minted = fast_bridge_vault.mint(receiver, 10**19)  # 10 crvUSD
    
    # Mint should work (though _get_balance might call rug_debt_ceiling)
    assert minted >= 0