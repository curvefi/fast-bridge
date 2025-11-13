import boa

import json
import os

from getpass import getpass
from eth_account import account


L2_NETWORK = (
    f"https://arb-mainnet.g.alchemy.com/v2/{os.environ['WEB3_ARBITRUM_MAINNET_ALCHEMY_API_KEY']}"  # ALTER
)
ETH_NETWORK = f"https://eth-mainnet.alchemyapi.io/v2/{os.environ['WEB3_ETHEREUM_MAINNET_ALCHEMY_PROJECT_ID']}"  # ALTER
API_KEY = os.environ["ETHERSCAN_V2_TOKEN"]

IERC20 = boa.load_abi("interfaces/IERC20.json")
CRVUSD_L2 = "0x498Bf2B1e120FeD3ad3D42EA2165E9b73f99C1e5"  # ALTER
CRVUSD = "0xf939E0A03FB07F59A73314E73794Be0E57ac1b4E"
AMOUNT = 10 ** 18  # Amount of crvUSD to test with

FAST_BRIDGE_VAULT = "0xadB10d2d5A95e58Ddb1A0744a0d2D7B55Db7843D"  # ALTER
FAST_BRIDGE_L2 = "0x1F2aF270029d028400265Ce1dd0919BA8780dAe1"  # ALTER


def seed(fast_bridge_vault=FAST_BRIDGE_VAULT):
    crvusd = IERC20.at(CRVUSD)
    if crvusd.balanceOf(fast_bridge_vault) < AMOUNT:
        crvusd.transfer(fast_bridge_vault, AMOUNT)
        print(f"Transferred {AMOUNT/10**18:.2f} crvUSD")
    else:
        print("Enough crvUSD in Vault")


def initiate_fast_bridge(fast_bridge_l2=FAST_BRIDGE_L2):
    crvusd = IERC20.at(CRVUSD_L2)
    crvusd.approve(fast_bridge_l2, AMOUNT)

    fast_bridge_l2 = boa.load_partial("contracts/FastBridgeL2.vy").at(FAST_BRIDGE_L2)
    bridger = boa.load_partial("contracts/bridgers/ArbitrumBridger.vy").at("0x8A5a5299f35614Ac558AA290C2d5856EDeC1B5Ad")
    fast_bridge_l2.bridge(crvusd, boa.env.eoa, AMOUNT, value=fast_bridge_l2.cost())
    print("Fast Bridge started")


def retry(fast_bridge_vault=FAST_BRIDGE_VAULT):
    crvusd = IERC20.at(CRVUSD)
    fast_bridge_vault = boa.load_partial("contracts/FastBridgeVault.vy").at(fast_bridge_vault)

    bal = crvusd.balanceOf(boa.env.eoa)
    fast_bridge_vault.mint(boa.env.eoa, 0)
    new_bal = crvusd.balanceOf(boa.env.eoa)
    print(f"Retry resulted with new {(new_bal-bal)/10**18:.2f} crvUSD")


def account_load(fname):
    path = os.path.expanduser(os.path.join("~", ".brownie", "accounts", fname + ".json"))
    with open(path, "r") as f:
        pkey = account.decode_keyfile_json(json.load(f), getpass())
        return account.Account.from_key(pkey)


def set_env(simulation: bool, mainnet: bool):
    if simulation:
        boa.fork(ETH_NETWORK if mainnet else L2_NETWORK, block_identifier="latest", allow_dirty=True)
        boa.env.eoa = "0x71F718D3e4d1449D1502A6A7595eb84eBcCB1683"
    else:
        boa.set_network_env(ETH_NETWORK if mainnet else L2_NETWORK)
        boa.env.add_account(account_load('curve'))


def test_seeded(simulate):
    set_env(simulate, True)
    seed()

    set_env(simulate, False)
    initiate_fast_bridge()


def test_emptied(simulate):
    set_env(simulate, False)
    initiate_fast_bridge()
    print("Now wait...")

    set_env(simulate, True)
    seed()
    retry()


if __name__ == "__main__":
    simulate = True
    # simulate = False

    test_seeded(simulate)
    # test_emptied(simulate)
