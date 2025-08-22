"""Integration tests for FastBridgeL2 allowed_to_bridge function."""

import pytest
import boa
from eth_utils import to_wei



def test_allowed_to_bridge_basic(forked_env, fast_bridge_l2, dev_deployer):
    """Test basic allowed_to_bridge functionality."""
    # Set up known values
    with boa.env.prank(dev_deployer):
        fast_bridge_l2.set_limit(1000 * 10 ** 18)
        fast_bridge_l2.set_min_amount(10 * 10 ** 18)
    
    # Get allowed range
    min_allowed, max_allowed = fast_bridge_l2.allowed_to_bridge()
    
    # Should return the full range when nothing has been bridged
    assert min_allowed == 10 * 10 ** 18
    assert max_allowed == 1000 * 10 ** 18



def test_allowed_to_bridge_after_bridging(forked_env, fast_bridge_l2, crvusd, dev_deployer):
    """Test allowed_to_bridge after some bridging has occurred."""
    # Set up
    with boa.env.prank(dev_deployer):
        fast_bridge_l2.set_limit(1000 * 10 ** 18)
        fast_bridge_l2.set_min_amount(10 * 10 ** 18)
    
    # Fund and bridge some amount
    boa.deal(crvusd, dev_deployer, 500 * 10 ** 18)
    boa.env.set_balance(dev_deployer, 10 * 10 ** 18)

    with boa.env.prank(dev_deployer):
        crvusd.approve(fast_bridge_l2.address, 500 * 10 ** 18)
    
    receiver = boa.env.generate_address()
    cost = fast_bridge_l2.cost()
    
    # Bridge 300 crvUSD
    with boa.env.prank(dev_deployer):
        fast_bridge_l2.bridge(crvusd, receiver, 300 * 10 ** 18, value=cost)
    
    # Check allowed range
    min_allowed, max_allowed = fast_bridge_l2.allowed_to_bridge()
    
    # Should have 700 crvUSD left in limit
    assert min_allowed == 10 * 10 ** 18
    assert max_allowed == 700 * 10 ** 18



def test_allowed_to_bridge_limit_exhausted(forked_env, fast_bridge_l2, crvusd, dev_deployer):
    """Test allowed_to_bridge when daily limit is exhausted."""
    # Set up low limit
    with boa.env.prank(dev_deployer):
        fast_bridge_l2.set_limit(100 * 10 ** 18)
        fast_bridge_l2.set_min_amount(10 * 10 ** 18)
    
    # Fund and bridge some amount
    boa.deal(crvusd, dev_deployer, 200 * 10 ** 18)
    boa.env.set_balance(dev_deployer, 10 * 10 ** 18)
    with boa.env.prank(dev_deployer):
        crvusd.approve(fast_bridge_l2.address, 200 * 10 ** 18)
    
    receiver = boa.env.generate_address()
    cost = fast_bridge_l2.cost()
    
    # Bridge the full limit
    with boa.env.prank(dev_deployer):
        fast_bridge_l2.bridge(crvusd, receiver, 100 * 10 ** 18, value=cost)
    
    # Check allowed range
    min_allowed, max_allowed = fast_bridge_l2.allowed_to_bridge()
    
    # Should return (0, 0) as limit is exhausted
    assert min_allowed == 0
    assert max_allowed == 0



def test_allowed_to_bridge_with_contract_balance(forked_env, fast_bridge_l2, crvusd, dev_deployer):
    """Test allowed_to_bridge when contract has existing balance."""
    # Set up
    with boa.env.prank(dev_deployer):
        fast_bridge_l2.set_limit(1000 * 10 ** 18)
        fast_bridge_l2.set_min_amount(100 * 10 ** 18)
    
    # Send some crvUSD directly to the contract (simulating someone sending by mistake)
    boa.deal(crvusd, fast_bridge_l2.address, 50 * 10 ** 18)
    boa.env.set_balance(dev_deployer, 10 * 10 ** 18)

    # Check allowed range
    min_allowed, max_allowed = fast_bridge_l2.allowed_to_bridge()
    
    # Min amount should not be reduced by the contract balance
    assert min_allowed == 100 * 10 ** 18
    assert max_allowed == 1000 * 10 ** 18
    
    # Send more to make balance exceed min_amount
    boa.deal(crvusd, fast_bridge_l2.address, 110 * 10 ** 18)  # Total 110
    
    min_allowed, max_allowed = fast_bridge_l2.allowed_to_bridge()
    
    # Min amount should not be reduced by the contract balance
    assert min_allowed == 100 * 10 ** 18
    assert max_allowed == 1000 * 10 ** 18



def test_allowed_to_bridge_insufficient_for_min(forked_env, fast_bridge_l2, crvusd, dev_deployer):
    """Test allowed_to_bridge when available is less than min_amount."""
    # Set up with high min_amount
    with boa.env.prank(dev_deployer):
        fast_bridge_l2.set_limit(1000 * 10 ** 18)
        fast_bridge_l2.set_min_amount(200 * 10 ** 18)
    
    # Fund and bridge some amount
    boa.deal(crvusd, dev_deployer, 850 * 10 ** 18)
    boa.env.set_balance(dev_deployer, 10 * 10 ** 18)
    with boa.env.prank(dev_deployer):
        crvusd.approve(fast_bridge_l2.address, 850 * 10 ** 18)
    
    receiver = boa.env.generate_address()
    cost = fast_bridge_l2.cost()
    
    # Bridge 850 crvUSD, leaving only 150 available (less than min 200)
    with boa.env.prank(dev_deployer):
        fast_bridge_l2.bridge(crvusd, receiver, 850 * 10 ** 18, value=cost)
    
    # Check allowed range
    min_allowed, max_allowed = fast_bridge_l2.allowed_to_bridge()
    
    # Should return (0, 0) as available (150) < min_amount (200)
    assert min_allowed == 0
    assert max_allowed == 0



def test_allowed_to_bridge_with_timestamp(forked_env, fast_bridge_l2, crvusd, dev_deployer):
    """Test allowed_to_bridge with custom timestamp parameter."""
    # Set up
    with boa.env.prank(dev_deployer):
        fast_bridge_l2.set_limit(1000 * 10 ** 18)
        fast_bridge_l2.set_min_amount(10 * 10 ** 18)
    
    # Get current timestamp
    current_ts = boa.eval("block.timestamp")
    
    # Test with current timestamp (should be same as default)
    min_default, max_default = fast_bridge_l2.allowed_to_bridge()
    min_current, max_current = fast_bridge_l2.allowed_to_bridge(current_ts)
    
    assert min_default == min_current
    assert max_default == max_current
    
        # Fund and bridge some amount
    boa.deal(crvusd, dev_deployer, 200 * 10 ** 18)
    boa.env.set_balance(dev_deployer, 10 * 10 ** 18)
    with boa.env.prank(dev_deployer):
        crvusd.approve(fast_bridge_l2.address, 200 * 10 ** 18)
    
    receiver = boa.env.generate_address()
    cost = fast_bridge_l2.cost()
    
    # Bridge the full limit
    with boa.env.prank(dev_deployer):
        fast_bridge_l2.bridge(crvusd, receiver, 100 * 10 ** 18, value=cost)
    
    min_current, max_current = fast_bridge_l2.allowed_to_bridge(current_ts)
    assert max_current < max_default
    
    # Test with future timestamp (next interval)
    future_ts = current_ts + 7 * 86400  # Next week
    min_future, max_future = fast_bridge_l2.allowed_to_bridge(future_ts)
    
    # Future interval should have full limit available
    assert min_future == min_default
    assert max_future == max_default