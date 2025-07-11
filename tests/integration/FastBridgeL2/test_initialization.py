"""Integration tests for FastBridgeL2 initialization and setup."""

import pytest
import boa
from conftest import to_bytes32


def test_basic_initialization(forked_env, fast_bridge_l2, crvusd, fast_bridge_vault, bridger, l2_messenger):
    """Test basic contract initialization."""
    # Check immutable values
    assert fast_bridge_l2.CRVUSD() == crvusd.address
    assert fast_bridge_l2.VAULT() == fast_bridge_vault.address
    
    # Check initial settings
    assert fast_bridge_l2.min_amount() == 10**18
    assert fast_bridge_l2.limit() == 10**18
    assert fast_bridge_l2.bridger() == bridger.address
    assert fast_bridge_l2.messenger() == l2_messenger.address
    
    # Check version
    assert fast_bridge_l2.version() == "0.0.1"



def test_setup_for_messaging(forked_env, fast_bridge_l2, l2_messenger, dev_deployer):
    """Test setting up messenger for proper operation."""
    # L2Messenger needs to have a peer set to work properly
    # This is required for quote_message_fee to work
    
    # Set a peer on the messenger (simulating L1 setup)
    test_eid = 30101  # Ethereum mainnet EID
    test_peer = to_bytes32(fast_bridge_l2.address)  # Using L2 address as peer for testing
    
    with boa.env.prank(dev_deployer):
        l2_messenger.setPeer(test_eid, test_peer)
    
    # Now quote_messaging_fee should work
    fee = fast_bridge_l2.quote_messaging_fee()
    assert isinstance(fee, int)
    assert fee >= 0