"""Integration tests for FastBridgeL2 allowed_to_bridge function."""

import pytest
import boa
from eth_utils import to_wei



def test_allowed_to_bridge_basic(forked_env, fast_bridge_l2, dev_deployer):
    """Test basic allowed_to_bridge functionality."""
    # Set up known values
    with boa.env.prank(dev_deployer):
        fast_bridge_l2.set_limit(to_wei(1000, "ether"))
        fast_bridge_l2.set_min_amount(to_wei(10, "ether"))
    
    # Get allowed range
    min_allowed, max_allowed = fast_bridge_l2.allowed_to_bridge()
    
    # Should return the full range when nothing has been bridged
    assert min_allowed == to_wei(10, "ether")
    assert max_allowed == to_wei(1000, "ether")



def test_allowed_to_bridge_after_bridging(forked_env, fast_bridge_l2, crvusd, dev_deployer):
    """Test allowed_to_bridge after some bridging has occurred."""
    # Set up
    with boa.env.prank(dev_deployer):
        fast_bridge_l2.set_limit(to_wei(1000, "ether"))
        fast_bridge_l2.set_min_amount(to_wei(10, "ether"))
    
    # Fund and bridge some amount
    boa.deal(crvusd, dev_deployer, to_wei(500, "ether"))
    boa.env.set_balance(dev_deployer, to_wei(10, "ether"))

    with boa.env.prank(dev_deployer):
        crvusd.approve(fast_bridge_l2.address, to_wei(500, "ether"))
    
    receiver = boa.env.generate_address()
    messaging_fee = fast_bridge_l2.quote_messaging_fee()
    
    # Bridge 300 crvUSD
    with boa.env.prank(dev_deployer):
        fast_bridge_l2.bridge(receiver, to_wei(300, "ether"), value=messaging_fee)
    
    # Check allowed range
    min_allowed, max_allowed = fast_bridge_l2.allowed_to_bridge()
    
    # Should have 700 crvUSD left in limit
    assert min_allowed == to_wei(10, "ether")
    assert max_allowed == to_wei(700, "ether")



def test_allowed_to_bridge_limit_exhausted(forked_env, fast_bridge_l2, crvusd, dev_deployer):
    """Test allowed_to_bridge when daily limit is exhausted."""
    # Set up low limit
    with boa.env.prank(dev_deployer):
        fast_bridge_l2.set_limit(to_wei(100, "ether"))
        fast_bridge_l2.set_min_amount(to_wei(10, "ether"))
    
    # Fund and bridge some amount
    boa.deal(crvusd, dev_deployer, to_wei(200, "ether"))
    boa.env.set_balance(dev_deployer, to_wei(10, "ether"))
    with boa.env.prank(dev_deployer):
        crvusd.approve(fast_bridge_l2.address, to_wei(200, "ether"))
    
    receiver = boa.env.generate_address()
    messaging_fee = fast_bridge_l2.quote_messaging_fee()
    
    # Bridge the full limit
    with boa.env.prank(dev_deployer):
        fast_bridge_l2.bridge(receiver, to_wei(100, "ether"), value=messaging_fee)
    
    # Check allowed range
    min_allowed, max_allowed = fast_bridge_l2.allowed_to_bridge()
    
    # Should return (0, 0) as limit is exhausted
    assert min_allowed == 0
    assert max_allowed == 0



def test_allowed_to_bridge_with_contract_balance(forked_env, fast_bridge_l2, crvusd, dev_deployer):
    """Test allowed_to_bridge when contract has existing balance."""
    # Set up
    with boa.env.prank(dev_deployer):
        fast_bridge_l2.set_limit(to_wei(1000, "ether"))
        fast_bridge_l2.set_min_amount(to_wei(100, "ether"))
    
    # Send some crvUSD directly to the contract (simulating someone sending by mistake)
    boa.deal(crvusd, fast_bridge_l2.address, to_wei(50, "ether"))
    boa.env.set_balance(dev_deployer, to_wei(10, "ether"))

    # Check allowed range
    min_allowed, max_allowed = fast_bridge_l2.allowed_to_bridge()
    
    # Min amount should be reduced by the contract balance
    assert min_allowed == to_wei(50, "ether")
    assert max_allowed == to_wei(1000, "ether")
    
    # Send more to make balance exceed min_amount
    boa.deal(crvusd, fast_bridge_l2.address, to_wei(110, "ether"))  # Total 110
    
    min_allowed, max_allowed = fast_bridge_l2.allowed_to_bridge()
    
    # Min amount should be 0 as balance exceeds min_amount
    assert min_allowed == 0
    assert max_allowed == to_wei(1000, "ether")



def test_allowed_to_bridge_insufficient_for_min(forked_env, fast_bridge_l2, crvusd, dev_deployer):
    """Test allowed_to_bridge when available is less than min_amount."""
    # Set up with high min_amount
    with boa.env.prank(dev_deployer):
        fast_bridge_l2.set_limit(to_wei(1000, "ether"))
        fast_bridge_l2.set_min_amount(to_wei(200, "ether"))
    
    # Fund and bridge some amount
    boa.deal(crvusd, dev_deployer, to_wei(850, "ether"))
    boa.env.set_balance(dev_deployer, to_wei(10, "ether"))
    with boa.env.prank(dev_deployer):
        crvusd.approve(fast_bridge_l2.address, to_wei(850, "ether"))
    
    receiver = boa.env.generate_address()
    messaging_fee = fast_bridge_l2.quote_messaging_fee()
    
    # Bridge 850 crvUSD, leaving only 150 available (less than min 200)
    with boa.env.prank(dev_deployer):
        fast_bridge_l2.bridge(receiver, to_wei(850, "ether"), value=messaging_fee)
    
    # Check allowed range
    min_allowed, max_allowed = fast_bridge_l2.allowed_to_bridge()
    
    # Should return (0, 0) as available (150) < min_amount (200)
    assert min_allowed == 0
    assert max_allowed == 0



def test_allowed_to_bridge_with_timestamp(forked_env, fast_bridge_l2, crvusd, dev_deployer):
    """Test allowed_to_bridge with custom timestamp parameter."""
    # Set up
    with boa.env.prank(dev_deployer):
        fast_bridge_l2.set_limit(to_wei(1000, "ether"))
        fast_bridge_l2.set_min_amount(to_wei(10, "ether"))
    
    # Get current timestamp
    current_ts = boa.eval("block.timestamp")
    
    # Test with current timestamp (should be same as default)
    min_default, max_default = fast_bridge_l2.allowed_to_bridge()
    min_current, max_current = fast_bridge_l2.allowed_to_bridge(current_ts)
    
    assert min_default == min_current
    assert max_default == max_current
    
        # Fund and bridge some amount
    boa.deal(crvusd, dev_deployer, to_wei(200, "ether"))
    boa.env.set_balance(dev_deployer, to_wei(10, "ether"))
    with boa.env.prank(dev_deployer):
        crvusd.approve(fast_bridge_l2.address, to_wei(200, "ether"))
    
    receiver = boa.env.generate_address()
    messaging_fee = fast_bridge_l2.quote_messaging_fee()
    
    # Bridge the full limit
    with boa.env.prank(dev_deployer):
        fast_bridge_l2.bridge(receiver, to_wei(100, "ether"), value=messaging_fee)
    
    min_current, max_current = fast_bridge_l2.allowed_to_bridge(current_ts)
    assert max_current < max_default
    
    # Test with future timestamp (next interval)
    future_ts = current_ts + 7 * 86400  # Next week
    min_future, max_future = fast_bridge_l2.allowed_to_bridge(future_ts)
    
    # Future interval should have full limit available
    assert min_future == min_default
    assert max_future == max_default