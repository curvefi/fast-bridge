# pragma version 0.4.3
"""
@title Curve Arbitrum Bridge Wrapper
@notice L2 -> L1
"""
import IBridger
from ethereum.ercs import IERC20

implements: IBridger

interface L2Gateway:
    def outboundTransfer(_l1_token: address, _to: address, _amount: uint256, _data: Bytes[1]): payable

interface StandardArbERC20:
    def l2Gateway() -> address: view
    def l1Address() -> address: view


@payable
@external
def bridge(_token: IERC20, _to: address, _amount: uint256, _min_amount: uint256=0) -> uint256:
    """
    @notice Bridge a token to Optimism mainnet using the L1 Standard Bridge
    @param _token The token to bridge
    @param _to The address to deposit the token to on L2
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

    gateway: address = staticcall StandardArbERC20(_token.address).l2Gateway()
    if staticcall _token.allowance(self, gateway) < amount:
        extcall _token.approve(gateway, max_value(uint256))

    extcall L2Gateway(gateway).outboundTransfer(
            staticcall StandardArbERC20(_token.address).l1Address(),
            _to,
            amount,
            b"",  # the inboundEscrowAndCall functionality has been disabled, so no data is allowed
    )
    return amount


@view
@external
def cost() -> uint256:
    """
    @notice Cost in ETH to bridge
    """
    return 0
