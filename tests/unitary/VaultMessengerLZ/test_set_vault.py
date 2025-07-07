import boa

def test_set_vault(vault_messenger, dev_deployer, fast_bridge_vault):
    assert vault_messenger.vault() == boa.eval('empty(address)')

    with boa.env.prank(dev_deployer):
        vault_messenger.set_vault(fast_bridge_vault.address)

    assert vault_messenger.vault() == fast_bridge_vault.address

def test_set_vault_not_owner(vault_messenger, alice, fast_bridge_vault):
    with boa.env.prank(alice):
        with boa.reverts('ownable: caller is not the owner'):
            vault_messenger.set_vault(fast_bridge_vault.address)