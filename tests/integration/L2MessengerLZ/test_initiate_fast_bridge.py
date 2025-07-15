import boa
from conftest import to_bytes32


def test_default_behavior(forked_env, l2_messenger, dev_deployer, fast_bridge_l2):
    # Setup peers for testing
    vault_eid = l2_messenger.VAULT_EID()
    with boa.env.prank(dev_deployer):
        peer_bytes = to_bytes32(l2_messenger.address) # set peer to self (vanity deployment)
        l2_messenger.setPeer(vault_eid, peer_bytes)
        l2_messenger.set_fast_bridge_l2(fast_bridge_l2.address)

    test_peer = boa.env.generate_address()
    to_mint = 10**18
    # give eth to sender
    boa.env.set_balance(fast_bridge_l2.address, 10**20)
    with boa.env.prank(fast_bridge_l2.address):
        l2_messenger.initiate_fast_bridge(test_peer, to_mint, dev_deployer, value=10**18)

    # test not bridge
    sender = boa.env.generate_address()
    boa.env.set_balance(sender, 10**20)

    with boa.env.prank(sender):
        with boa.reverts('Only FastBridgeL2!'):
            l2_messenger.initiate_fast_bridge(test_peer, to_mint, dev_deployer, value=10**18)
