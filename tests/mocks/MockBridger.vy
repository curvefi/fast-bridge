# pragma version 0.4.3

from ethereum.ercs import IERC20

@external
def initiate_bridge(asset: address, to: address, amount: uint256, min_amount: uint256) -> uint256:
    extcall IERC20(asset).transferFrom(msg.sender, self, amount, default_return_value=True)
    return 0
