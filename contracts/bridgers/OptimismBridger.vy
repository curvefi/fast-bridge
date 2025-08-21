# pragma version 0.4.3

"""
@title Curve Optimism Bridge Wrapper
@notice L2 -> L1
"""

import IBridger
from ethereum.ercs import IERC20

implements: IBridger

interface IStandardBridge:
    def bridgeERC20To(_localToken: address, _remoteToken: address, _to: address, _amount: uint256, _minGasLimit: uint32, _extraData: Bytes[1]): nonpayable

interface IOptimismMintableERC20:
    def REMOTE_TOKEN() -> address: view
    def BRIDGE() -> IStandardBridge: view


# OPTIMISM_L2_BRIDGE: constant(address) = 0x4200000000000000000000000000000000000010


@payable
@external
def bridge(_token: IERC20, _to: address, _amount: uint256, _min_amount: uint256=0) -> uint256:
    """
    @notice Bridge a token to mainnet using the Standard Bridge
    @param _token The token to bridge
    @param _to The address to deposit the token to on L1
    @param _amount The amount of the token to deposit, 2^256-1 for the whole balance
    @param _min_amount Minimum amount to bridge
    """
    assert msg.value == 0, "Not supported"
    assert _to != empty(address), "Bad receiver"

    amount: uint256 = _amount
    if amount == max_value(uint256):
        amount = staticcall _token.balanceOf(msg.sender)
    assert amount >= _min_amount
    assert extcall _token.transferFrom(msg.sender, self, amount, default_return_value=True)

    bridge: IStandardBridge = staticcall IOptimismMintableERC20(_token.address).BRIDGE()
    if staticcall _token.allowance(self, bridge.address) < amount:
        extcall _token.approve(bridge.address, max_value(uint256))

    extcall bridge.bridgeERC20To(
            _token.address,
            staticcall IOptimismMintableERC20(_token.address).REMOTE_TOKEN(),
            _to,
            amount,
            250_000,  # Gas to use to complete the transfer on the receiving side.
            b"",  # Optional identify extra data.
    )

    log IBridger.Bridge(token=_token, sender=msg.sender, receiver=_to, amount=amount)
    return amount


@view
@external
def cost() -> uint256:
    """
    @notice Cost in ETH to bridge
    """
    return 0
