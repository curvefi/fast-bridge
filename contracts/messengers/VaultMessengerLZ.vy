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

initializes: OApp[ownable := ownable]
exports: (
    OApp.endpoint,
    OApp.peers,
    OApp.setPeer,
    OApp.setDelegate,
    OApp.isComposeMsgSender,
    OApp.allowInitializePath,
    OApp.nextNonce,
)

interface IVault:
    def mint(_receiver: address, _amount: uint256) -> uint256: nonpayable

vault: public(IVault)

@deploy
def __init__(_endpoint: address):
    """
    @notice Initialize messenger with LZ endpoint and default gas settings
    @param _endpoint LayerZero endpoint address
    """
    ownable.__init__()
    ownable._transfer_ownership(tx.origin)

    OApp.__init__(_endpoint, tx.origin)


@external
def set_vault(_vault: address):
    """
    @notice Set vault address
    @param _vault new vault address
    """
    ownable._check_owner()
    self.vault = IVault(_vault)


@payable
@external
def lzReceive(
    _origin: OApp.Origin,
    _guid: bytes32,
    _message: Bytes[OApp.MAX_MESSAGE_SIZE],
    _executor: address,
    _extraData: Bytes[OApp.MAX_EXTRA_DATA_SIZE],
):
    """
    @notice Receive message from main chain
    @param _origin Origin information containing srcEid, sender, and nonce
    @param _guid Global unique identifier for the message
    @param _message The encoded message payload containing to and amount
    @param _executor Address of the executor for the message
    @param _extraData Additional data passed by the executor
    """
    # Verify message source
    OApp._lzReceive(_origin, _guid, _message, _executor, _extraData)

    # Decode message
    to: address = empty(address)
    amount: uint256 = empty(uint256)
    to, amount = abi_decode(_message, (address, uint256))

    # Pass mint command to vault
    extcall self.vault.mint(to, amount)




# @payable
# @external
# def lzReceive(
#     _origin: OApp.Origin,
#     _guid: bytes32,
#     _message: Bytes[OApp.MAX_MESSAGE_SIZE],
#     _executor: address,
#     _extraData: Bytes[OApp.MAX_EXTRA_DATA_SIZE],
# ):
#     """
#     @notice Handle messages: read responses, and regular messages
#     @dev Two types of messages:
#          1. Read responses (from read channel)
#          2. Regular messages (block hash broadcasts from other chains)
#     @param _origin Origin information containing srcEid, sender, and nonce
#     @param _guid Global unique identifier for the message
#     @param _message The encoded message payload containing block number and hash
#     @param _executor Address of the executor for the message
#     @param _extraData Additional data passed by the executor
#     """
#     # Verify message source
#     OApp._lzReceive(_origin, _guid, _message, _executor, _extraData)

#     if _origin.srcEid == self.read_channel:
#         # Only handle read response if read is enabled
#         assert self.read_enabled, "Read not enabled"
#         # Decode block hash and number from response
#         block_number: uint256 = 0
#         block_hash: bytes32 = empty(bytes32)
#         block_number, block_hash = abi_decode(_message, (uint256, bytes32))
#         if block_hash == empty(bytes32):
#             return  # Invalid response

#         # Store received block hash
#         self.received_blocks[block_number] = block_hash

#         # Commit block hash to oracle
#         self._commit_block(block_number, block_hash)

#         broadcast_data: BroadcastData = self.broadcast_data[_guid]

#         if len(broadcast_data.targets) > 0:
#             # Verify that attached value covers requested broadcast fees
#             total_fee: uint256 = 0
#             for target: BroadcastTarget in broadcast_data.targets:
#                 total_fee += target.fee
#             assert msg.value >= total_fee, "Insufficient msg.value"

#             # Perform broadcast
#             self._broadcast_block(
#                 block_number,
#                 block_hash,
#                 broadcast_data,
#                 self, # dev: refund excess fee to self
#             )
#     else:
#         # Regular message - decode and commit block hash
#         block_number: uint256 = 0
#         block_hash: bytes32 = empty(bytes32)
#         block_number, block_hash = abi_decode(_message, (uint256, bytes32))
#         self._commit_block(block_number, block_hash)
