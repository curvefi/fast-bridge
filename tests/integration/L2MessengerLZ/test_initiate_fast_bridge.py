import boa
from conftest import to_bytes32

# @external
# @payable
# def initiate_fast_bridge(_to: address, _amount: uint256):
#     """
#     @notice Initiate fast bridge by sending (to, amount) to peer on main chain
#     Only callable by FastBridgeL2
#     @param _to Address to mint to
#     @param _amount Amount to mint
#     """
#     assert msg.sender == self.fast_bridge_l2, "Only FastBridgeL2!"
    
#      # step 1: convert message to bytes
#     encoded_message: Bytes[OApp.MAX_MESSAGE_SIZE] = abi_encode(_to, _amount)

#     # step 2: create options using OptionsBuilder module
#     options: Bytes[OptionsBuilder.MAX_OPTIONS_TOTAL_SIZE] = OptionsBuilder.newOptions()
#     options = OptionsBuilder.addExecutorLzReceiveOption(options, self.gas_limit, 0)

#     # step 3: send message
#     fees: OApp.MessagingFee = OApp.MessagingFee(nativeFee=msg.value, lzTokenFee=0)
#     OApp._lzSend(VAULT_EID, encoded_message, options, fees, msg.sender)


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