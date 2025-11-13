import boa

import json
import os
from eth_abi import encode
from web3 import Web3

from getpass import getpass
from eth_account import account


L2_NETWORK = (
    f"https://opt-mainnet.g.alchemy.com/v2/{os.environ['WEB3_OPTIMISM_MAINNET_ALCHEMY_API_KEY']}"
)
ETH_NETWORK = f"https://eth-mainnet.alchemyapi.io/v2/{os.environ['WEB3_ETHEREUM_MAINNET_ALCHEMY_PROJECT_ID']}"
API_KEY = os.environ["ETHERSCAN_V2_TOKEN"]

LZ_ENDPOINT = "0x1a44076050125825900e736c501f859c50fE728c"  # L1 (Ethereum)

OWNERSHIP_DAO = "0x40907540d8a6C65c637785e8f8B742ae6b0b9968"
EMERGENCY_DAO = "0x467947EE34aF926cF1DCac093870f613C96B1E0c"

L2_OWNER = "0x28c4A1Fa47EEE9226F8dE7D6AF0a41C62Ca98267"  # ALTER


def deploy_l1():
    vault_messenger = (boa.load_partial("contracts/messengers/VaultMessengerLZ.vy")
                       .deploy(LZ_ENDPOINT))
                       # .at("0x4A10d0FF9e394f3A3dCdb297973Db40Ce304b44f"))  # noqa
    fast_bridge_vault = (boa.load_partial("contracts/FastBridgeVault.vy")
                         .deploy(OWNERSHIP_DAO, EMERGENCY_DAO, [vault_messenger]))
                         # .at("0x97d024859B68394122B3d0bb407dD7299cC8E937"))  # noqa
    vault_messenger.set_vault(fast_bridge_vault)

    print(
        f"Deployment on L1:\n"
        f"  FastBridgeVault: {fast_bridge_vault.address}\n"
        f"  VaultMessengerLZ: {vault_messenger.address}\n"
    )
    return fast_bridge_vault, vault_messenger


def deploy_l2(fast_bridge_vault):
    lz_endpoint = "0x1a44076050125825900e736c501f859c50fE728c"  # ALTER: https://docs.layerzero.network/v2/deployments/deployed-contracts?chains=
    vault_eid = 30101  # Vault Endpoint ID (Ethereum)
    gas_limit = 200_000
    l2_messenger = (boa.load_partial("contracts/messengers/L2MessengerLZ.vy")
                    .deploy(lz_endpoint, vault_eid, gas_limit))
                    # .at("0x345BBb82a124A2ab64aD515605274F36b6e5aB3e"))  # noqa
    bridger = (boa.load_partial("contracts/bridgers/OptimismBridger.vy")
               .deploy())
               # .at("0x5dfafda4d5b26be0e99e6a8c6b1eb97ed99b9bd3"))  # noqa
    crvusd = "0xC52D7F23a2e460248Db6eE192Cb23dD12bDDCbf6"  # ALTER: crvusd address on L2
    fast_bridge_l2 = (boa.load_partial("contracts/FastBridgeL2.vy")
                      .deploy(crvusd, fast_bridge_vault, bridger, l2_messenger))
                      # .at("0x60F542FCdCb5Edb26a42514A8434CE4c772F2fd7"))  # noqa
    l2_messenger.set_fast_bridge_l2(fast_bridge_l2)

    print(
        f"Deployment on L2:\n"
        f"  FastBridgeL2: {fast_bridge_l2.address}\n"
        f"  L2MessengerLZ: {l2_messenger.address}\n"
        f"  Bridger: {bridger.address}\n"
    )
    return fast_bridge_l2, l2_messenger, bridger


def setup_l1(vault_messenger_lz, l2_messenger_lz):
    vault_messenger = boa.load_partial("contracts/messengers/VaultMessengerLZ.vy").at(vault_messenger_lz)

    l2_eid = 30111  # ALTER: https://docs.layerzero.network/v2/deployments/deployed-contracts?chains=
    vault_messenger.setPeer(
        l2_eid,  # eid
        Web3.to_bytes(hexstr=l2_messenger_lz),  # peer
    )

    endpoint = boa.from_etherscan(LZ_ENDPOINT, api_key=API_KEY)
    vault_messenger.setDelegate(boa.env.eoa)

    required_dvns = [
        "0x589dedbd617e0cbcb916a9223f4d1300c294236b",  # LayerZero Labs
        "0xcc35923c43893cc31f2815e216afd7efb60f1fb0",  # Swiss Stake
    ]
    optional_dvns = []
    required_dvns = sorted([Web3.to_checksum_address(addr) for addr in required_dvns])
    optional_dvns = sorted([Web3.to_checksum_address(addr) for addr in optional_dvns])
    config_struct = (
        0,  # confirmations (uint64)
        len(required_dvns),
        len(optional_dvns),
        len(optional_dvns) if optional_dvns else 0,
        required_dvns,
        optional_dvns,
    )
    endpoint.setConfig(
        vault_messenger_lz,  # oapp
        "0xc02Ab410f0734EFa3F14628780e6e695156024C2",  # ReceiveUln302 lib
        [
            (
                l2_eid,  # eid
                2,  # configType (ULN for send/receive)
                encode(["(uint64,uint8,uint8,uint8,address[],address[])"], [config_struct]),  # config
            )
        ]
    )

    print("L1 Setup Complete!")


def setup_l2(vault_messenger_lz, l2_messenger_lz):
    l2_messenger = boa.load_partial("contracts/messengers/L2MessengerLZ.vy").at(l2_messenger_lz)

    l1_eid = 30101  # Ethereum
    l2_messenger.setPeer(
        l1_eid,  # eid
        Web3.to_bytes(hexstr=vault_messenger_lz),  # peer
    )

    endpoint = boa.from_etherscan(LZ_ENDPOINT, api_key=API_KEY)
    l2_messenger.setDelegate(boa.env.eoa)
    required_dvns = [
        "0x6a02d83e8d433304bba74ef1c427913958187142",  # ALTER: LayerZero Labs
        "0xb908fc507fe3145e855cf63127349756b9ecf3a6",  # ALTER: Swiss Stake
    ]
    optional_dvns = []
    required_dvns = sorted([Web3.to_checksum_address(addr) for addr in required_dvns])
    optional_dvns = sorted([Web3.to_checksum_address(addr) for addr in optional_dvns])
    config_struct = (
        0,  # confirmations (uint64)
        len(required_dvns),
        len(optional_dvns),
        len(optional_dvns) if optional_dvns else 0,
        required_dvns,
        optional_dvns,
    )
    endpoint.setConfig(
        l2_messenger_lz,  # oapp
        "0x1322871e4ab09Bc7f5717189434f97bBD9546e95",  # ALTER: SendUln302 lib
        [
            (
                l1_eid,  # eid
                2,  # configType (ULN for send/receive)
                encode(["(uint64,uint8,uint8,uint8,address[],address[])"], [config_struct]),  # config
            )
        ]
    )

    print("L2 Setup Complete!")


def set_limits(fast_bridge_l2):
    fast_bridge_l2 = boa.load_partial("contracts/FastBridgeL2.vy").at(fast_bridge_l2)

    fast_bridge_l2.set_min_amount(10 * 10 ** 18)
    fast_bridge_l2.set_limit((200_000 // 4) * 10 ** 18)  # ALTER


def revoke_ownership_l1(fast_bridge_vault, vault_messenger_lz):
    fast_bridge_vault = boa.load_partial("contracts/FastBridgeVault.vy").at(fast_bridge_vault)
    # Should be revoked at deployment
    if fast_bridge_vault.hasRole(fast_bridge_vault.DEFAULT_ADMIN_ROLE(), boa.env.eoa):
        fast_bridge_vault.revokeRole(fast_bridge_vault.DEFAULT_ADMIN_ROLE(), boa.env.eoa)

    vault_messenger = boa.load_partial("contracts/messengers/VaultMessengerLZ.vy").at(vault_messenger_lz)
    vault_messenger.setDelegate(OWNERSHIP_DAO)
    vault_messenger.transfer_ownership(OWNERSHIP_DAO)

    print("Ownership on L1 transferred")


def revoke_ownership_l2(fast_bridge_l2, l2_messenger_lz):
    fast_bridge_l2 = boa.load_partial("contracts/FastBridgeL2.vy").at(fast_bridge_l2)
    fast_bridge_l2.transfer_ownership(L2_OWNER)

    l2_messenger = boa.load_partial("contracts/messengers/L2MessengerLZ.vy").at(l2_messenger_lz)
    l2_messenger.setDelegate(L2_OWNER)
    l2_messenger.transfer_ownership(L2_OWNER)

    print("Ownership on L2 transferred")


def account_load(fname):
    path = os.path.expanduser(os.path.join("~", ".brownie", "accounts", fname + ".json"))
    with open(path, "r") as f:
        pkey = account.decode_keyfile_json(json.load(f), getpass())
        return account.Account.from_key(pkey)


def set_env(simulation: bool, mainnet: bool):
    if simulation:
        boa.fork(ETH_NETWORK if mainnet else L2_NETWORK, block_identifier="latest")
        boa.env.eoa = "0x71F718D3e4d1449D1502A6A7595eb84eBcCB1683"
    else:
        boa.set_network_env(ETH_NETWORK if mainnet else L2_NETWORK)
        boa.env.add_account(account_load('curve'))


if __name__ == "__main__":
    simulate = True
    # simulate = False

    # L1
    set_env(simulate, True)

    fast_bridge_vault, vault_messenger = deploy_l1()
    # fast_bridge_vault = "0x97d024859B68394122B3d0bb407dD7299cC8E937"
    # vault_messenger = "0x4A10d0FF9e394f3A3dCdb297973Db40Ce304b44f"

    # L2
    set_env(simulate, False)

    fast_bridge_l2, l2_messenger, bridger = deploy_l2(fast_bridge_vault)
    # fast_bridge_l2 = "0x60F542FCdCb5Edb26a42514A8434CE4c772F2fd7"
    # l2_messenger = "0x345BBb82a124A2ab64aD515605274F36b6e5aB3e"
    setup_l2(vault_messenger, l2_messenger)

    # set_limits(fast_bridge_l2)

    # revoke_ownership_l2(fast_bridge_l2, l2_messenger)

    # L1
    set_env(simulate, True)
    setup_l1(vault_messenger, l2_messenger)

    # revoke_ownership_l1(fast_bridge_vault, vault_messenger)
