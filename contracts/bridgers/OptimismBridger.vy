# pragma version 0.4.3
"""
@title Curve Optimism Bridge Wrapper
@notice L1 -> L2
"""
from ethereum.ercs import IERC20
from snekmate.auth import ownable

initializes: ownable
exports: (
    ownable.owner,
    ownable.transfer_ownership,
    ownable.renounce_ownership,
)


interface OptimismL1Bridge:
    def depositERC20To(
        _l1Token: address,
        _l2Token: address,
        _to: address,
        _amount: uint256,
        _l2Gas: uint32,
        _data: Bytes[1]
    ): nonpayable


event UpdateTokenMapping:
    _l1_token: indexed(address)
    _old_l2_token: address
    _new_l2_token: address


CRV20: immutable(IERC20)
L2_CRV20: immutable(address)
OPTIMISM_L1_BRIDGE: immutable(address)


# l1_token -> l2_token
l2_token: public(HashMap[IERC20, address])
l2_gas: public(uint32)


@deploy
def __init__(_l2_crv: address, _optimism_l1_bridge: address):
    ownable.__init__()
    ownable._transfer_ownership(tx.origin)
    
    CRV20 = IERC20(0xD533a949740bb3306d119CC777fa900bA034cd52)
    L2_CRV20 = _l2_crv
    OPTIMISM_L1_BRIDGE = _optimism_l1_bridge

    assert extcall CRV20.approve(_optimism_l1_bridge, max_value(uint256))
    self.l2_token[CRV20] = L2_CRV20
    self.l2_gas = 200_000


@external
def bridge(_token: IERC20, _to: address, _amount: uint256, _min_amount: uint256=0):
    """
    @notice Bridge a token to Optimism mainnet using the L1 Standard Bridge
    @param _token The token to bridge
    @param _to The address to deposit the token to on L2
    @param _amount The amount of the token to deposit, 2^256-1 for the whole balance
    @param _min_amount Minimum amount to bridge
    """
    amount: uint256 = _amount
    if amount == max_value(uint256):
        amount = staticcall _token.balanceOf(msg.sender)
    assert amount >= _min_amount
    assert extcall _token.transferFrom(msg.sender, self, amount, default_return_value=True)

    l2_token: address = L2_CRV20
    if _token != CRV20:
        l2_token = self.l2_token[_token]
        assert l2_token != empty(address)  # dev: token not mapped

    extcall OptimismL1Bridge(OPTIMISM_L1_BRIDGE).depositERC20To(
        _token.address,
        l2_token,
        _to,
        amount,
        self.l2_gas,
        b""
    )


@view
@external
def check(_account: address) -> bool:
    """
    @notice Dummy method to check if caller is allowed to bridge
    @param _account The account to check
    """
    return True


@view
@external
def cost() -> uint256:
    """
    @notice Cost in ETH to bridge
    """
    return 0


@external
def set_l2_token(_l1_token: IERC20, _l2_token: address):
    """
    @notice Set the mapping of L1 token -> L2 token for depositing
    @param _l1_token The l1 token address
    @param _l2_token The l2 token address
    """
    ownable._check_owner()
    assert _l1_token != CRV20  # dev: cannot reset mapping for CRV20

    amount: uint256 = 0
    if _l2_token != empty(address):
        amount = max_value(uint256)
    assert extcall _l1_token.approve(OPTIMISM_L1_BRIDGE, amount)

    log UpdateTokenMapping(_l1_token=_l1_token.address, _old_l2_token=self.l2_token[_l1_token], _new_l2_token=_l2_token)
    self.l2_token[_l1_token] = _l2_token


@external
def set_gas(_l2_gas: uint32):
    """
    @notice Set the L2 gas limit for deposits
    @param _l2_gas The new L2 gas limit
    """
    ownable._check_owner()
    self.l2_gas = _l2_gas