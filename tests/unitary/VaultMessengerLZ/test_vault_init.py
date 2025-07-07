
def test_init(vault_messenger, dev_deployer, lz_endpoint):
    assert vault_messenger.owner() == dev_deployer
    assert vault_messenger.endpoint() == lz_endpoint.address

