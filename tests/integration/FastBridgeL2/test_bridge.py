"""Integration tests for FastBridgeL2 bridge function."""

import boa
from eth_utils import to_wei


def test_bridge_basic(forked_env, fast_bridge_l2, crvusd, l2_messenger, dev_deployer):
    """Test basic bridge functionality."""
    # Setup test data
    bridge_amount = 1000 * 10 ** 18  # 1000 crvUSD
    receiver = boa.env.generate_address()
    
    # Set a higher limit to allow the bridge
    with boa.env.prank(dev_deployer):
        fast_bridge_l2.set_limit(10000 * 10 ** 18)
    
    # Fund the deployer with crvUSD
    boa.deal(crvusd, dev_deployer, bridge_amount * 2)
    boa.env.set_balance(dev_deployer, 10 * 10 ** 18)
    
    # Check initial balance
    assert crvusd.balanceOf(dev_deployer) >= bridge_amount
    
    # Approve FastBridge to spend crvUSD
    with boa.env.prank(dev_deployer):
        crvusd.approve(fast_bridge_l2.address, bridge_amount)
    
    # Get messaging fee
    messaging_fee = fast_bridge_l2.quote_messaging_fee()
    
    initial_user_balance = crvusd.balanceOf(dev_deployer)
    
    # Execute bridge
    with boa.env.prank(dev_deployer):
        bridged_amount = fast_bridge_l2.bridge(receiver, bridge_amount, value=messaging_fee)
    
    # Verify the bridged amount
    assert bridged_amount == bridge_amount
    
    # Verify crvUSD was transferred from user
    assert crvusd.balanceOf(dev_deployer) == initial_user_balance - bridge_amount
    
    # The tokens are now in the bridger contract, not FastBridgeL2
    # This is because FastBridgeL2 transfers them to the bridger in line 109
    bridger_balance = crvusd.balanceOf(fast_bridge_l2.bridger())
    assert bridger_balance == bridge_amount
    
    # Verify daily limit was updated
    interval = 86400  # 1 day
    current_interval = boa.eval("block.timestamp") // interval
    assert fast_bridge_l2.bridged(current_interval) == bridge_amount


def test_bridge_max_balance(forked_env, fast_bridge_l2, crvusd, dev_deployer):
    """Test bridging with max_value (entire balance)."""
    # Fund the deployer with crvUSD
    test_amount = 5000 * 10 ** 18
    boa.deal(crvusd, dev_deployer, test_amount)
    boa.env.set_balance(dev_deployer, 10 * 10 ** 18)
    
    # Approve more than balance
    with boa.env.prank(dev_deployer):
        crvusd.approve(fast_bridge_l2.address, test_amount * 2)
    
    receiver = boa.env.generate_address()
    messaging_fee = fast_bridge_l2.quote_messaging_fee()
    
    user_balance_before = crvusd.balanceOf(dev_deployer)
    
    # Bridge with max_value to use entire balance
    with boa.env.prank(dev_deployer):
        # First check the current limit
        interval = 86400
        current_interval = boa.eval("block.timestamp") // interval
        already_bridged = fast_bridge_l2.bridged(current_interval)
        limit = fast_bridge_l2.limit()
        available = limit - already_bridged
        
        # Bridge with max_value
        bridged_amount = fast_bridge_l2.bridge(
            receiver, 
            boa.eval("max_value(uint256)"), 
            value=messaging_fee
        )
    
    # Should bridge the minimum of: balance, allowance, and available limit
    expected = min(user_balance_before, available)
    assert bridged_amount == expected
    assert crvusd.balanceOf(dev_deployer) == user_balance_before - bridged_amount


def test_bridge_with_daily_limit(forked_env, fast_bridge_l2, crvusd, dev_deployer):
    """Test bridge respects daily limit."""
    # Set a low daily limit
    with boa.env.prank(dev_deployer):
        fast_bridge_l2.set_limit(100 * 10 ** 18)  # 100 crvUSD limit
    
    # Fund the deployer
    boa.deal(crvusd, dev_deployer, 1000 * 10 ** 18)
    boa.env.set_balance(dev_deployer, 10 * 10 ** 18)
    
    # Approve
    with boa.env.prank(dev_deployer):
        crvusd.approve(fast_bridge_l2.address, 1000 * 10 ** 18)
    
    receiver = boa.env.generate_address()
    messaging_fee = fast_bridge_l2.quote_messaging_fee()
    
    # Try to bridge more than the limit
    with boa.env.prank(dev_deployer):
        bridged_amount = fast_bridge_l2.bridge(
            receiver,
            200 * 10 ** 18,  # More than limit
            value=messaging_fee
        )
    
    # Should only bridge up to the limit
    assert bridged_amount == 100 * 10 ** 18
    
    # Try to bridge again in the same interval
    with boa.env.prank(dev_deployer):
        bridged_amount2 = fast_bridge_l2.bridge(
            receiver,
            50 * 10 ** 18,
            value=messaging_fee
        )
    
    # Should bridge 0 as limit is exhausted
    assert bridged_amount2 == 0


def test_bridge_min_amount_requirement(forked_env, fast_bridge_l2, crvusd, dev_deployer):
    """Test bridge fails when amount is below minimum after limit application."""
    # Set up a scenario where available < min_amount
    with boa.env.prank(dev_deployer):
        fast_bridge_l2.set_limit(150 * 10 ** 18)
        fast_bridge_l2.set_min_amount(100 * 10 ** 18)
    
    # Fund and approve
    boa.deal(crvusd, dev_deployer, 1000 * 10 ** 18)
    boa.env.set_balance(dev_deployer, 10 * 10 ** 18)
    
    with boa.env.prank(dev_deployer):
        crvusd.approve(fast_bridge_l2.address, 1000 * 10 ** 18)
    
    receiver = boa.env.generate_address()
    messaging_fee = fast_bridge_l2.quote_messaging_fee()
    
    # First bridge to use up some limit
    with boa.env.prank(dev_deployer):
        fast_bridge_l2.bridge(receiver, 60 * 10 ** 18, value=messaging_fee)
    
    # Now only 90 crvUSD available (less than min_amount of 100)
    # Try to bridge with a _min_amount requirement
    with boa.env.prank(dev_deployer):
        with boa.reverts():
            fast_bridge_l2.bridge(
                receiver,
                150 * 10 ** 18,
                100 * 10 ** 18,  # min_amount parameter
                value=messaging_fee
            )


def test_bridge_events(forked_env, fast_bridge_l2, crvusd, dev_deployer):
    """Test that bridge emits correct events."""
    # Fund and setup
    bridge_amount = 100 * 10 ** 18
    boa.deal(crvusd, dev_deployer, bridge_amount)
    boa.env.set_balance(dev_deployer, 10 * 10 ** 18)
    
    with boa.env.prank(dev_deployer):
        crvusd.approve(fast_bridge_l2.address, bridge_amount)
    
    receiver = boa.env.generate_address()
    messaging_fee = fast_bridge_l2.quote_messaging_fee()
    
    # Execute bridge
    with boa.env.prank(dev_deployer):
        fast_bridge_l2.bridge(receiver, bridge_amount, value=messaging_fee)
    
    # Get logs after function call
    events = fast_bridge_l2.get_logs()
    
    # Note: Specific event checking would depend on the exact events emitted
    # by the bridger and messenger contracts. For now, we verify the transaction succeeded.
    # In a real test, you would check for specific events like Transfer, Bridge, etc.
    assert len(events) > 0  # At least some events should be emitted


def test_bridge_insufficient_messaging_fee(forked_env, fast_bridge_l2, crvusd, dev_deployer):
    """Test bridge fails with insufficient messaging fee."""
    # Fund and setup
    bridge_amount = 100 * 10 ** 18
    boa.deal(crvusd, dev_deployer, bridge_amount)
    boa.env.set_balance(dev_deployer, 10 * 10 ** 18)
    
    with boa.env.prank(dev_deployer):
        crvusd.approve(fast_bridge_l2.address, bridge_amount)
    
    receiver = boa.env.generate_address()
    messaging_fee = fast_bridge_l2.quote_messaging_fee()
    
    # Try to bridge with less than required messaging fee
    with boa.env.prank(dev_deployer):
        with boa.reverts():
            fast_bridge_l2.bridge(
                receiver,
                bridge_amount,
                value=messaging_fee // 2  # Half the required fee
            )