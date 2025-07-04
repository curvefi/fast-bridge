
def test_default_behavior(fast_bridge_l2, crvusd, fast_bridge_vault, bridger, l2_messenger):
    assert fast_bridge_l2.CRVUSD() == crvusd.address
    assert fast_bridge_l2.VAULT() == fast_bridge_vault.address
    assert fast_bridge_l2.bridger() == bridger.address
    assert fast_bridge_l2.messenger() == l2_messenger.address
    assert fast_bridge_l2.min_amount() == 10**18
    assert fast_bridge_l2.limit() == 10**18

