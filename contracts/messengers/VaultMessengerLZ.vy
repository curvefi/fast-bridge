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
    OApp.setReadChannel,
    OApp.isComposeMsgSender,
    OApp.allowInitializePath,
    OApp.nextNonce,
)

@deploy
def __init__(_endpoint: address):
    """
    @notice Initialize messenger with LZ endpoint and default gas settings
    @param _endpoint LayerZero endpoint address
    """
    ownable.__init__()
    ownable._transfer_ownership(tx.origin)

    OApp.__init__(_endpoint, tx.origin)
