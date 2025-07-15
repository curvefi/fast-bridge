# pragma version 0.4.3
"""
@notice Curve Harmony Bridge Wrapper
"""
from ethereum.ercs import IERC20


interface HarmonyBridge:
    def lockToken(_token: address, _amount: uint256, _receiver: address): nonpayable


CRV20: constant(address) = 0xD533a949740bb3306d119CC777fa900bA034cd52
HARMONY_BRIDGE: constant(address) = 0x2dCCDB493827E15a5dC8f8b72147E6c4A5620857


# token -> is approval given to bridge
is_approved: public(HashMap[address, bool])


@deploy
def __init__():
    assert extcall IERC20(CRV20).approve(HARMONY_BRIDGE, max_value(uint256))
    self.is_approved[CRV20] = True


@external
def bridge(_token: address, _to: address, _amount: uint256):
    """
    @notice Bridge a token to Harmony mainnet
    @param _token The token to bridge
    @param _to The address to deposit the token to on harmony
    @param _amount The amount of the token to bridge
    """
    assert extcall IERC20(_token).transferFrom(msg.sender, self, _amount)

    if _token != CRV20 and not self.is_approved[_token]:
        assert extcall IERC20(_token).approve(HARMONY_BRIDGE, max_value(uint256))
        self.is_approved[_token] = True

    extcall HarmonyBridge(HARMONY_BRIDGE).lockToken(_token, _amount, _to)


@pure
@external
def cost() -> uint256:
    """
    @notice Cost in ETH to bridge
    """
    return 0


@pure
@external
def check(_account: address) -> bool:
    """
    @notice Check if `_account` is allowed to bridge
    @param _account The account to check
    """
    return True