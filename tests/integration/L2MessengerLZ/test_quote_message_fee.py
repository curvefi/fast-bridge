import boa
from conftest import to_bytes32


def test_default_behavior(forked_env, l2_messenger, dev_deployer):
    # Setup peers for testing
    vault_eid = l2_messenger.vault_eid()
    test_peer = boa.env.generate_address()

    with boa.env.prank(dev_deployer):
        peer_bytes = to_bytes32(test_peer)
        l2_messenger.setPeer(vault_eid, peer_bytes)

    # Quote fees for chains with peers
    fees = l2_messenger.quote_message_fee()

    assert isinstance(fees, int)
    assert fees > 0


def test_no_peer(forked_env, l2_messenger, dev_deployer):
    vault_eid = l2_messenger.vault_eid()
    with boa.env.prank(dev_deployer):
        peer_bytes = to_bytes32(boa.eval("empty(address)"))
        l2_messenger.setPeer(vault_eid, peer_bytes)

    with boa.reverts('OApp: no peer'):
        l2_messenger.quote_message_fee()
