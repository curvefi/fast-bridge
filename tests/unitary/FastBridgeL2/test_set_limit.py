import boa

def test_default_behavior(fast_bridge_l2, dev_deployer):
    assert fast_bridge_l2.limit() == 10**18
    new_limit = 10**19
    with boa.env.prank(dev_deployer):
        fast_bridge_l2.set_limit(new_limit)
    assert fast_bridge_l2.limit() == new_limit

def test_set_limit_not_owner(fast_bridge_l2):
    new_limit = 10**19
    with boa.env.prank(boa.env.generate_address()):
        with boa.reverts('ownable: caller is not the owner'):
            fast_bridge_l2.set_limit(new_limit)