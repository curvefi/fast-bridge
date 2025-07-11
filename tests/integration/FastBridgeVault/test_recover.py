"""Integration tests for FastBridgeVault recover function."""

import boa


def test_recover_single_token(forked_env, fast_bridge_vault, curve_dao, crvusd):
    """Test recovering a single token."""
    recovery_receiver = boa.env.generate_address()
    
    # Fund the vault with crvUSD
    amount = 1000 * 10**18
    boa.deal(crvusd, fast_bridge_vault.address, amount)
    
    initial_vault_balance = crvusd.balanceOf(fast_bridge_vault.address)
    
    # Prepare recovery input
    recovery_input = [(crvusd.address, amount)]
    
    # Recover as admin
    with boa.env.prank(curve_dao):
        fast_bridge_vault.recover(recovery_input, recovery_receiver)
    
    # Verify recovery
    assert crvusd.balanceOf(recovery_receiver) == amount
    assert crvusd.balanceOf(fast_bridge_vault.address) == initial_vault_balance - amount


def test_recover_max_value(forked_env, fast_bridge_vault, curve_dao, crvusd):
    """Test recovering with max_value to get entire balance."""
    recovery_receiver = boa.env.generate_address()
    
    # Fund the vault
    amount = 1234567 * 10**15  # 1234.567 * 10**18
    boa.deal(crvusd, fast_bridge_vault.address, amount)
    
    # Recover using max_value (2**256 - 1)
    max_uint256 = 2**256 - 1
    recovery_input = [(crvusd.address, max_uint256)]
    
    with boa.env.prank(curve_dao):
        fast_bridge_vault.recover(recovery_input, recovery_receiver)
    
    # Should recover entire balance
    assert crvusd.balanceOf(recovery_receiver) == amount
    assert crvusd.balanceOf(fast_bridge_vault.address) == 0


def test_recover_multiple_tokens(forked_env, fast_bridge_vault, curve_dao, crvusd):
    """Test recovering multiple tokens in one call."""
    recovery_receiver = boa.env.generate_address()
    
    # Deploy mock ERC20 tokens
    mock_token_code = """
# pragma version 0.4.3

from ethereum.ercs import IERC20

implements: IERC20

name: public(String[32])
symbol: public(String[32])
decimals: public(uint8)
totalSupply: public(uint256)
balanceOf: public(HashMap[address, uint256])
allowance: public(HashMap[address, HashMap[address, uint256]])
@deploy
def __init__(_name: String[32], _symbol: String[32]):
    self.name = _name
    self.symbol = _symbol
    self.decimals = 18
    self.totalSupply = 10**25  # 10M tokens
    self.balanceOf[msg.sender] = self.totalSupply

@external
def transfer(_to: address, _value: uint256) -> bool:
    self.balanceOf[msg.sender] -= _value
    self.balanceOf[_to] += _value
    return True

@external
def transferFrom(_from: address, _to: address, _value: uint256) -> bool:
    self.allowance[_from][msg.sender] -= _value
    self.balanceOf[_from] -= _value
    self.balanceOf[_to] += _value
    return True

@external
def approve(_spender: address, _value: uint256) -> bool:
    self.allowance[msg.sender][_spender] = _value
    return True
"""
    
    # Deploy two mock tokens
    with boa.env.prank(curve_dao):
        token1 = boa.loads_partial(mock_token_code).deploy("Token1", "TK1")
        token2 = boa.loads_partial(mock_token_code).deploy("Token2", "TK2")
    
    # Fund vault with both tokens and crvUSD
    amounts = [100 * 10**18, 200 * 10**18, 300 * 10**18]
    
    # Fund crvUSD
    boa.deal(crvusd, fast_bridge_vault.address, amounts[0])
    
    # Fund tokens from deployer
    with boa.env.prank(curve_dao):
        token1.transfer(fast_bridge_vault.address, amounts[1])
        token2.transfer(fast_bridge_vault.address, amounts[2])
    
    # Prepare recovery inputs
    recovery_inputs = [
        (crvusd.address, amounts[0]),
        (token1.address, amounts[1]),
        (token2.address, amounts[2])
    ]
    
    # Recover all tokens
    with boa.env.prank(curve_dao):
        fast_bridge_vault.recover(recovery_inputs, recovery_receiver)
    
    # Verify all recoveries
    assert crvusd.balanceOf(recovery_receiver) == amounts[0]
    assert token1.balanceOf(recovery_receiver) == amounts[1]
    assert token2.balanceOf(recovery_receiver) == amounts[2]
    
    # Vault should be empty
    assert crvusd.balanceOf(fast_bridge_vault.address) == 0
    assert token1.balanceOf(fast_bridge_vault.address) == 0
    assert token2.balanceOf(fast_bridge_vault.address) == 0


def test_recover_unauthorized(forked_env, fast_bridge_vault, crvusd):
    """Test recover fails for unauthorized caller."""
    unauthorized = boa.env.generate_address()
    recovery_receiver = boa.env.generate_address()
    
    # Fund the vault
    boa.deal(crvusd, fast_bridge_vault.address, 1000 * 10**18)
    
    recovery_input = [(crvusd.address, 1000 * 10**18)]
    
    with boa.env.prank(unauthorized):
        with boa.reverts("access_control: account is missing role"):
            fast_bridge_vault.recover(recovery_input, recovery_receiver)


def test_recover_partial_amounts(forked_env, fast_bridge_vault, curve_dao, crvusd):
    """Test recovering partial amounts."""
    recovery_receiver = boa.env.generate_address()
    
    # Fund the vault
    total_amount = 1000 * 10**18
    boa.deal(crvusd, fast_bridge_vault.address, total_amount)
    
    # Recover only part of the balance
    recover_amount = 600 * 10**18
    recovery_input = [(crvusd.address, recover_amount)]
    
    with boa.env.prank(curve_dao):
        fast_bridge_vault.recover(recovery_input, recovery_receiver)
    
    # Verify partial recovery
    assert crvusd.balanceOf(recovery_receiver) == recover_amount
    assert crvusd.balanceOf(fast_bridge_vault.address) == total_amount - recover_amount


def test_recover_empty_list(forked_env, fast_bridge_vault, curve_dao):
    """Test recover with empty list."""
    recovery_receiver = boa.env.generate_address()
    
    # Call recover with empty list
    with boa.env.prank(curve_dao):
        fast_bridge_vault.recover([], recovery_receiver)
    
    # Should complete without errors (no-op)