import boa

def test_default_behavior(l2_messenger, dev_deployer, fast_bridge_l2):
    assert l2_messenger.vault_eid() != 123456
    with boa.env.prank(dev_deployer):
        l2_messenger.set_vault_eid(123456)

    assert l2_messenger.vault_eid() == 123456

def test_not_owner(l2_messenger, dev_deployer):
    with boa.env.prank(boa.env.generate_address()):
        with boa.reverts('ownable: caller is not the owner'):
            l2_messenger.set_vault_eid(123456)