"""Integration tests for FastBridgeL2 admin functions."""

import pytest
import boa
from eth_utils import to_wei


def test_set_min_amount(forked_env, fast_bridge_l2, dev_deployer):
    """Test set_min_amount functionality."""
    # Check initial min_amount
    initial_min = fast_bridge_l2.min_amount()
    assert initial_min == 1 * 10 ** 18  # Default from constructor
    
    # Set new min_amount as owner
    new_min = 50 * 10 ** 18
    with boa.env.prank(dev_deployer):
        fast_bridge_l2.set_min_amount(new_min)
    
    # Verify change
    assert fast_bridge_l2.min_amount() == new_min
    

def test_set_min_amount_unauthorized(forked_env, fast_bridge_l2):
    """Test set_min_amount fails for non-owner."""
    unauthorized = boa.env.generate_address()
    
    with boa.env.prank(unauthorized):
        with boa.reverts("ownable: caller is not the owner"):
            fast_bridge_l2.set_min_amount(100 * 10 ** 18)


def test_set_limit(forked_env, fast_bridge_l2, dev_deployer):
    """Test set_limit functionality."""
    # Check initial limit
    initial_limit = fast_bridge_l2.limit()
    assert initial_limit == 1 * 10 ** 18  # Default from constructor
    
    # Set new limit as owner
    new_limit = 10000 * 10 ** 18
    with boa.env.prank(dev_deployer):
        fast_bridge_l2.set_limit(new_limit)

    events = fast_bridge_l2.get_logs()

    # Verify change
    assert fast_bridge_l2.limit() == new_limit
    
    # Check event emission
    assert any(
        "SetLimit" in str(event) and str(new_limit) in str(event)
        for event in events
    ), "SetLimit event not emitted"

def test_set_limit_unauthorized(forked_env, fast_bridge_l2):
    """Test set_limit fails for non-owner."""
    unauthorized = boa.env.generate_address()
    
    with boa.env.prank(unauthorized):
        with boa.reverts("ownable: caller is not the owner"):
            fast_bridge_l2.set_limit(5000 * 10 ** 18)


def test_set_bridger(forked_env, fast_bridge_l2, crvusd, dev_deployer):
    """Test set_bridger functionality."""

    # Deploy a new mock bridger
    new_bridger = boa.env.generate_address()
    # Get initial bridger
    initial_bridger = fast_bridge_l2.bridger()
    
    # Check initial approval
    initial_approval = crvusd.allowance(fast_bridge_l2.address, initial_bridger)
    assert initial_approval > 0
    
    # Set new bridger
    with boa.env.prank(dev_deployer):
        fast_bridge_l2.set_bridger(new_bridger)
    events = fast_bridge_l2.get_logs()

    # Verify change
    assert fast_bridge_l2.bridger() == new_bridger
    
    # Check approvals were updated
    assert crvusd.allowance(fast_bridge_l2.address, initial_bridger) == 0
    assert crvusd.allowance(fast_bridge_l2.address, new_bridger) == boa.eval("max_value(uint256)")
    
    # Check event emission
    assert any(
        "SetBridger" in str(event) and str(new_bridger) in str(event)
        for event in events
    ), "SetBridger event not emitted"


def test_set_bridger_unauthorized(forked_env, fast_bridge_l2):
    """Test set_bridger fails for non-owner."""
    unauthorized = boa.env.generate_address()
    mock_bridger = boa.env.generate_address()
    
    with boa.env.prank(unauthorized):
        with boa.reverts("ownable: caller is not the owner"):
            fast_bridge_l2.set_bridger(mock_bridger)


def test_set_messenger(forked_env, fast_bridge_l2, dev_deployer):
    """Test set_messenger functionality."""
    new_messenger = boa.env.generate_address()
    # Set new messenger
    with boa.env.prank(dev_deployer):
        fast_bridge_l2.set_messenger(new_messenger)
    events = fast_bridge_l2.get_logs()

    # Verify change
    assert fast_bridge_l2.messenger() == new_messenger
        
    # Check event emission
    assert any(
        "SetMessenger" in str(event) and str(new_messenger) in str(event)
        for event in events
    ), "SetMessenger event not emitted"


def test_set_messenger_unauthorized(forked_env, fast_bridge_l2):
    """Test set_messenger fails for non-owner."""
    unauthorized = boa.env.generate_address()
    mock_messenger = boa.env.generate_address()
    
    with boa.env.prank(unauthorized):
        with boa.reverts("ownable: caller is not the owner"):
            fast_bridge_l2.set_messenger(mock_messenger)


def test_ownership_transfer(forked_env, fast_bridge_l2, dev_deployer):
    """Test ownership transfer functionality."""
    # Check initial owner
    assert fast_bridge_l2.owner() == dev_deployer
    
    # Create new owner
    new_owner = boa.env.generate_address()
    
    # Transfer ownership
    with boa.env.prank(dev_deployer):
        fast_bridge_l2.transfer_ownership(new_owner)
    
    # Verify new owner
    assert fast_bridge_l2.owner() == new_owner
    
    # Verify old owner can't call admin functions
    with boa.env.prank(dev_deployer):
        with boa.reverts("ownable: caller is not the owner"):
            fast_bridge_l2.set_limit(1000 * 10 ** 18)
    
    # Verify new owner can call admin functions
    with boa.env.prank(new_owner):
        fast_bridge_l2.set_limit(2000 * 10 ** 18)
    
    assert fast_bridge_l2.limit() == 2000 * 10 ** 18