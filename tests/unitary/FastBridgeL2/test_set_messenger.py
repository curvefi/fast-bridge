import boa

def test_default_behavior(fast_bridge_l2, l2_messenger, dev_deployer):
    assert fast_bridge_l2.messenger() == l2_messenger.address
    new_messenger = boa.env.generate_address()
    with boa.env.prank(dev_deployer):
        fast_bridge_l2.set_messenger(new_messenger)
    assert fast_bridge_l2.messenger() == new_messenger

def test_set_messenger_not_owner(fast_bridge_l2, l2_messenger):
    new_messenger = boa.env.generate_address()
    with boa.env.prank(boa.env.generate_address()):
        with boa.reverts('ownable: caller is not the owner'):
            fast_bridge_l2.set_messenger(new_messenger)
    assert fast_bridge_l2.messenger() == l2_messenger.address