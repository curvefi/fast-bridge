import pytest
import boa
from boa import env


@pytest.fixture
def mock_token():
    return boa.load("tests/mocks/MockERC20.vy")


def test_recover_specific_amount(fast_bridge_vault, curve_dao, alice, mock_token):
    # Send tokens to vault
    amount = 10**20
    boa.deal(mock_token, fast_bridge_vault.address, amount)
    
    assert mock_token.balanceOf(fast_bridge_vault.address) == amount
    
    # Recover tokens
    receiver = env.generate_address()
    with boa.env.prank(curve_dao):
        fast_bridge_vault.recover([(mock_token.address, amount)], receiver)
    
    assert mock_token.balanceOf(fast_bridge_vault.address) == 0
    assert mock_token.balanceOf(receiver) == amount


def test_recover_max_amount(fast_bridge_vault, curve_dao, alice, mock_token):
    # Send tokens to vault
    amount = 10**20
    boa.deal(mock_token, fast_bridge_vault.address, amount)
    
    # Recover using max_value to get all tokens
    receiver = env.generate_address()
    with boa.env.prank(curve_dao):
        fast_bridge_vault.recover([(mock_token.address, 2**256 - 1)], receiver)
    
    assert mock_token.balanceOf(fast_bridge_vault.address) == 0
    assert mock_token.balanceOf(receiver) == amount


def test_recover_multiple_tokens(fast_bridge_vault, curve_dao, alice):
    # Create multiple tokens
    token1 = boa.load("tests/mocks/MockERC20.vy")
    token2 = boa.load("tests/mocks/MockERC20.vy")
    
    amount1 = 10**20
    amount2 = 2 * 10**20
    
    # Send tokens to vault
    boa.deal(token1, fast_bridge_vault.address, amount1)
    boa.deal(token2, fast_bridge_vault.address, amount2)
    
    # Recover both tokens
    receiver = env.generate_address()
    with boa.env.prank(curve_dao):
        fast_bridge_vault.recover([
            (token1.address, amount1),
            (token2.address, amount2)
        ], receiver)
    
    assert token1.balanceOf(receiver) == amount1
    assert token2.balanceOf(receiver) == amount2


def test_recover_unauthorized(fast_bridge_vault, alice, mock_token):
    # Non-admin cannot recover
    with boa.reverts():
        with boa.env.prank(alice):
            fast_bridge_vault.recover([(mock_token.address, 10**18)], alice)


def test_recover_crvusd(fast_bridge_vault, curve_dao, alice, crvusd):
    # Can also recover crvUSD
    amount = 10**20
    boa.deal(crvusd, fast_bridge_vault.address, amount)
    
    receiver = env.generate_address()
    with boa.env.prank(curve_dao):
        fast_bridge_vault.recover([(crvusd.address, amount)], receiver)
    
    assert crvusd.balanceOf(receiver) == amount