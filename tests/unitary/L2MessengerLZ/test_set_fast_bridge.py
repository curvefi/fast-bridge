import boa

def test_default_behavior(l2_messenger, dev_deployer, fast_bridge_l2):
    assert l2_messenger.fast_bridge_l2() == boa.eval("empty(address)")
    with boa.env.prank(dev_deployer):
        l2_messenger.set_fast_bridge_l2(fast_bridge_l2.address)

    assert l2_messenger.fast_bridge_l2() == fast_bridge_l2.address

def test_not_owner(l2_messenger, dev_deployer, fast_bridge_l2):
    with boa.env.prank(boa.env.generate_address()):
        with boa.reverts('ownable: caller is not the owner'):
            l2_messenger.set_fast_bridge_l2(fast_bridge_l2.address)