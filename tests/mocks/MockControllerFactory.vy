# pragma version 0.4.3

@external
def rug_debt_ceiling(_to: address):
    pass

@external
@view
def debt_ceiling(of: address) -> uint256:
    return 0

@external
@view
def debt_ceiling_residual(of: address) -> uint256:
    return 0