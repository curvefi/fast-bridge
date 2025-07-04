import boa

def test_default_behavior(fast_bridge_l2, bridger, dev_deployer):
    assert fast_bridge_l2.bridger() == bridger.address
    new_bridger = boa.env.generate_address()
    with boa.env.prank(dev_deployer):
        fast_bridge_l2.set_bridger(new_bridger)
    assert fast_bridge_l2.bridger() == new_bridger

def test_set_bridger_not_owner(fast_bridge_l2, bridger):
    new_bridger = boa.env.generate_address()
    with boa.env.prank(boa.env.generate_address()):
        with boa.reverts('ownable: caller is not the owner'):
            fast_bridge_l2.set_bridger(new_bridger)
    assert fast_bridge_l2.bridger() == bridger.address