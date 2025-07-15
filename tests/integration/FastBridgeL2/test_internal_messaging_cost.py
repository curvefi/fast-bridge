"""Integration tests for FastBridgeL2 quote_messaging_fee function."""

import pytest
import boa


def test_quote_messaging_fee_basic(forked_env, fast_bridge_l2):
    """Test basic quote_messaging_fee functionality."""
    # Get the messaging fee quote
    fee = fast_bridge_l2.internal.messaging_cost()
    
    # Fee should be a non-negative integer
    assert isinstance(fee, int)
    assert fee >= 0
    
    # In a forked mainnet environment, the fee might be 0 or a positive value
    # depending on the messenger configuration


def test_quote_messaging_fee_consistency(forked_env, fast_bridge_l2):
    """Test that quote_messaging_fee returns consistent results."""
    # Get multiple quotes
    fee1 = fast_bridge_l2.internal.messaging_cost()
    fee2 = fast_bridge_l2.internal.messaging_cost()
    fee3 = fast_bridge_l2.internal.messaging_cost()
    
    # Fees should be consistent (assuming no state changes)
    assert fee1 == fee2 == fee3



def test_quote_messaging_fee_after_messenger_change(forked_env, fast_bridge_l2, dev_deployer):
    """Test quote_messaging_fee after changing messenger."""
    # Get initial fee
    initial_fee = fast_bridge_l2.internal.messaging_cost()
    
    # Deploy a new mock messenger that returns a different fee
    mock_messenger_code = """
# pragma version 0.4.3

@external
@view
def quote_message_fee() -> uint256:
    return 123456789  # Fixed fee for testing

@external
@payable
def initiate_fast_bridge(_to: address, _amount: uint256, _lz_fee_refund: address):
    pass
"""
    
    with boa.env.prank(dev_deployer):
        mock_messenger = boa.loads_partial(mock_messenger_code).deploy()
        
        # Set the new messenger
        fast_bridge_l2.set_messenger(mock_messenger)
    
    # Get new fee
    new_fee = fast_bridge_l2.internal.messaging_cost()
    
    # Fee should be the one returned by the mock messenger
    assert new_fee == 123456789
    # new_fee should be different from initial_fee (unless by coincidence)



def test_quote_messaging_fee_with_different_messengers(forked_env, fast_bridge_l2, dev_deployer):
    """Test quote_messaging_fee with different messenger implementations."""
    # Create messengers with different fee structures
    messenger_codes = [
        # Zero fee messenger
        """
# pragma version 0.4.3

@external
@view
def quote_message_fee() -> uint256:
    return 0

@external
@payable
def initiate_fast_bridge(_to: address, _amount: uint256, _lz_fee_refund: address):
    pass
""",
        # High fee messenger
        """
# pragma version 0.4.3

@external
@view
def quote_message_fee() -> uint256:
    return 10**18  # 1 ETH

@external
@payable
def initiate_fast_bridge(_to: address, _amount: uint256, _lz_fee_refund: address):
    pass
""",
        # Dynamic fee messenger
        """
# pragma version 0.4.3

counter: uint256

@external
@view
def quote_message_fee() -> uint256:
    # Simulate dynamic fee based on some state
    return 10**15 * (self.counter + 1)

@external
@payable
def initiate_fast_bridge(_to: address, _amount: uint256, _lz_fee_refund: address):
    self.counter += 1
"""
    ]
    
    fees = []
    for code in messenger_codes:
        with boa.env.prank(dev_deployer):
            messenger = boa.loads_partial(code).deploy()
            fast_bridge_l2.set_messenger(messenger)
        
        fee = fast_bridge_l2.internal.messaging_cost()
        fees.append(fee)
    
    # Verify different messengers return different fees
    assert fees[0] == 0  # Zero fee
    assert fees[1] == 10**18  # 1 ETH
    assert fees[2] == 10**15  # Dynamic fee initial value