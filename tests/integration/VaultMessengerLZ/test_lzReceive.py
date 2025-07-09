import boa
from conftest import to_bytes32, LZ_ENDPOINT, LZ_EID

def test_lz_receive_no_crvusd(forked_env, vault_messenger, l2_messenger, fast_bridge_vault, dev_deployer):
    """Test handling a regular message in lzReceive."""
    # Setup the relay
    with boa.env.prank(dev_deployer):
        # Set block oracle
        vault_messenger.set_vault(fast_bridge_vault.address)

    # Create Origin struct from a remote EID 
    l2_eid = 999
    origin = (l2_eid, boa.eval(f"convert({l2_messenger.address}, bytes32)"), 0)
    guid = bytes(32)  # Empty bytes32 for test

    # Create a message with block data
    to_mint = 10**18
    receiver = boa.env.generate_address()
    message = boa.util.abi.abi_encode("(address,uint256)", (receiver, to_mint))

    # Add peer for the source chain to allow the message
    with boa.env.prank(dev_deployer):
        peer_bytes = to_bytes32(l2_messenger.address)
        vault_messenger.setPeer(l2_eid, peer_bytes)

    assert fast_bridge_vault.balanceOf(receiver) == 0

    # Call lzReceive directly (as if from the endpoint)
    with boa.env.prank(LZ_ENDPOINT):
        vault_messenger.lzReceive(origin, guid, message, dev_deployer, b"")

    assert fast_bridge_vault.balanceOf(receiver) == to_mint


def test_lz_receive_with_crvusd(forked_env, vault_messenger, l2_messenger, fast_bridge_vault, dev_deployer, crvusd):
    """Test handling a regular message in lzReceive."""
    # Setup the relay
    with boa.env.prank(dev_deployer):
        # Set block oracle
        vault_messenger.set_vault(fast_bridge_vault.address)

    # Create Origin struct from a remote EID 
    l2_eid = 999
    origin = (l2_eid, boa.eval(f"convert({l2_messenger.address}, bytes32)"), 0)
    guid = bytes(32)  # Empty bytes32 for test

    # Create a message with block data
    to_mint = 10**18
    receiver = boa.env.generate_address()
    message = boa.util.abi.abi_encode("(address,uint256)", (receiver, to_mint))

    # Add peer for the source chain to allow the message
    with boa.env.prank(dev_deployer):
        peer_bytes = to_bytes32(l2_messenger.address)
        vault_messenger.setPeer(l2_eid, peer_bytes)

    assert fast_bridge_vault.balanceOf(receiver) == 0
    assert crvusd.balanceOf(receiver) == 0
    assert crvusd.balanceOf(fast_bridge_vault.address) == 0

    boa.deal(crvusd, fast_bridge_vault.address, 100_000 * 10**18)
    # Call lzReceive directly (as if from the endpoint)
    with boa.env.prank(LZ_ENDPOINT):
        vault_messenger.lzReceive(origin, guid, message, dev_deployer, b"")

    assert crvusd.balanceOf(receiver) == to_mint
    assert crvusd.balanceOf(fast_bridge_vault.address) == 100_000 * 10**18 - to_mint