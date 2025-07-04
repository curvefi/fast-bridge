import boa

def test_default_behavior(fast_bridge_l2, dev_deployer):
    assert fast_bridge_l2.min_amount() == 10**18
    new_min_amount = 10**19
    with boa.env.prank(dev_deployer):
        fast_bridge_l2.set_min_amount(new_min_amount)
    assert fast_bridge_l2.min_amount() == new_min_amount

def test_set_min_amount_not_owner(fast_bridge_l2):
    new_min_amount = 10**19
    with boa.env.prank(boa.env.generate_address()):
        with boa.reverts('ownable: caller is not the owner'):
            fast_bridge_l2.set_min_amount(new_min_amount)
    assert fast_bridge_l2.min_amount() == 10**18