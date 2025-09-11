
def test_init(l2_messenger, dev_deployer, vault_eid, gas_limit):
    assert l2_messenger.vault_eid() == vault_eid
    assert l2_messenger.gas_limit() == gas_limit
    assert l2_messenger.owner() == dev_deployer
