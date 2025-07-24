# pragma version 0.4.3

# Import ownership management
from snekmate.auth import ownable

initializes: ownable
exports: (
    ownable.owner,
    ownable.transfer_ownership,
    ownable.renounce_ownership,
)

# LayerZero module
from ..modules.oapp_vyper.src import OApp
from ..modules.oapp_vyper.src import OptionsBuilder

initializes: OApp[ownable := ownable]
exports: (
    OApp.endpoint,
    OApp.peers,
    OApp.setPeer,
    OApp.setDelegate,
    OApp.setReadChannel,
    OApp.isComposeMsgSender,
    OApp.allowInitializePath,
    OApp.nextNonce,
)

VAULT_EID: public(immutable(uint32))
fast_bridge_l2: public(address)
gas_limit: public(uint128)


@deploy
def __init__(_endpoint: address, _vault_eid: uint32, _gas_limit: uint128):
    """
    @notice Initialize messenger with LZ endpoint and default gas settings
    @param _endpoint LayerZero endpoint address
    @param _vault_eid Vault chain EID
    @param _gas_limit Gas limit for lz message
    @dev after deployment, must call setPeer()
    """
    ownable.__init__()
    ownable._transfer_ownership(tx.origin)

    OApp.__init__(_endpoint, tx.origin)

    VAULT_EID = _vault_eid
    self.gas_limit = _gas_limit


@external
def set_fast_bridge_l2(_fast_bridge_l2: address):
    """
    @notice Set fast bridge l2 address
    @param _fast_bridge_l2 FastBridgeL2 address
    """
    ownable._check_owner()
    self.fast_bridge_l2 = _fast_bridge_l2


@external
def set_gas_limit(_gas_limit: uint128):
    """
    @notice Set gas limit for LZ message on destination chain
    @param _gas_limit Gas limit
    """
    ownable._check_owner()
    self.gas_limit = _gas_limit

    
@external
@view
def quote_message_fee() -> uint256:
    """
    @notice Quote message fee in native token
    """
    # step 1: mock message 
    encoded_message: Bytes[OApp.MAX_MESSAGE_SIZE] = abi_encode(self, empty(uint256))

    # step 2: mock options
    options: Bytes[OptionsBuilder.MAX_OPTIONS_TOTAL_SIZE] = OptionsBuilder.newOptions()
    options = OptionsBuilder.addExecutorLzReceiveOption(options, self.gas_limit, 0)

    # step 3: quote fee
    return OApp._quote(VAULT_EID, encoded_message, options, False).nativeFee


@external
@payable
def initiate_fast_bridge(_to: address, _amount: uint256, _lz_fee_refund: address):
    """
    @notice Initiate fast bridge by sending (to, amount) to peer on main chain
    Only callable by FastBridgeL2
    @param _to Address to mint to
    @param _amount Amount to mint
    """
    assert msg.sender == self.fast_bridge_l2, "Only FastBridgeL2!"
    
     # step 1: convert message to bytes
    encoded_message: Bytes[OApp.MAX_MESSAGE_SIZE] = abi_encode(_to, _amount)

    # step 2: create options using OptionsBuilder module
    options: Bytes[OptionsBuilder.MAX_OPTIONS_TOTAL_SIZE] = OptionsBuilder.newOptions()
    options = OptionsBuilder.addExecutorLzReceiveOption(options, self.gas_limit, 0)

    # step 3: send message
    fees: OApp.MessagingFee = OApp.MessagingFee(nativeFee=msg.value, lzTokenFee=0)
    OApp._lzSend(VAULT_EID, encoded_message, options, fees, _lz_fee_refund)
