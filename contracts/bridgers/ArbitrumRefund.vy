# pragma version 0.4.3
"""
@notice Curve Arbitrum Bridge Wrapper Refunder
"""
from snekmate.auth import ownable

initializes: ownable
exports: (
    ownable.owner,
    ownable.transfer_ownership,
    ownable.renounce_ownership,
)


@deploy
def __init__():
    ownable.__init__()
    ownable._transfer_ownership(tx.origin)


@payable
@external
def __default__():
    pass


@external
def withdraw(_receiver: address = msg.sender):
    """
    @notice Withdraw held funds to the owner address
    @dev If the owner is a contract it must be able to receive ETH
    """
    ownable._check_owner()
    send(_receiver, self.balance)