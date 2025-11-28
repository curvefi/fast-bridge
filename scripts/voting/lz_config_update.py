import os

import boa
from voting import vote, xvote, abi, OWNERSHIP, CustomEnv
from voting.xgov.chains import ARBITRUM, OPTIMISM, FRAXTAL

from getpass import getpass
from eth_account import account

import json

from web3 import Web3
from eth_abi import encode, decode

from LZMetadata import LZMetadata

DRPC_KEY = os.getenv("DRPC_API_KEY")
RPC_URL = f"https://lb.drpc.org/ethereum/{DRPC_KEY}"
ETHERSCAN_API_KEY = os.environ["ETHERSCAN_API_KEY"]
boa.fork(RPC_URL)
# boa.set_network_env(RPC_URL)
boa.env.eoa = "0x71F718D3e4d1449D1502A6A7595eb84eBcCB1683"


endpoint = boa.from_etherscan("0x1a44076050125825900e736c501f859c50fE728c", api_key=ETHERSCAN_API_KEY)

l1_dvns = [
    "0x589dedbd617e0cbcb916a9223f4d1300c294236b",  # LayerZero Labs
    "0xcc35923c43893cc31f2815e216afd7efb60f1fb0",  # Swiss Stake
]


def get_config(confirmations, required_dvns):
    optional_dvns = []
    required_dvns = sorted([Web3.to_checksum_address(addr) for addr in required_dvns])
    optional_dvns = sorted([Web3.to_checksum_address(addr) for addr in optional_dvns])
    config_struct = (
        confirmations,  # uint64
        len(required_dvns),
        len(optional_dvns),
        len(optional_dvns) if optional_dvns else 0,
        required_dvns,
        optional_dvns,
    )
    return encode(["(uint64,uint8,uint8,uint8,address[],address[])"], [config_struct])

CONFIG_TYPE_EXECUTOR = 1  # Executor configuration type
CONFIG_TYPE_ULN = 2  # ULN configuration type for send/receive
CONFIG_TYPE_READ = 1  # Read configuration type (same as executor but different context)
def checksum(address: str) -> str:
    """Convert address to checksum format"""
    return Web3.to_checksum_address(address)

def decode_dvn_config(hex_data: bytes, config_type: str = "uln"):
    """Decode DVN configuration from hex data"""
    if not hex_data or hex_data == "0x":
        return None

    if isinstance(hex_data, str):
        hex_data = bytes.fromhex(hex_data.replace("0x", ""))

    try:
        if config_type == "read":
            # Read config includes executor address
            decoded = decode(["(address,uint8,uint8,uint8,address[],address[])"], hex_data)
            return {
                "executor": checksum(decoded[0][0]),
                "requiredDVNCount": decoded[0][1],
                "optionalDVNCount": decoded[0][2],
                "optionalDVNThreshold": decoded[0][3],
                "requiredDVNs": [checksum(addr) for addr in decoded[0][4]],
                "optionalDVNs": [checksum(addr) for addr in decoded[0][5]],
            }
        elif config_type == "executor":
            # Executor config is just (uint32,address)
            decoded = decode(["(uint32,address)"], hex_data)
            return {"executor": checksum(decoded[0][1])}
        else:
            # ULN config for send/receive
            decoded = decode(["(uint64,uint8,uint8,uint8,address[],address[])"], hex_data)
            return {
                "confirmations": decoded[0][0],
                "requiredDVNCount": decoded[0][1],
                "optionalDVNCount": decoded[0][2],
                "optionalDVNThreshold": decoded[0][3],
                "requiredDVNs": [checksum(addr) for addr in decoded[0][4]],
                "optionalDVNs": [checksum(addr) for addr in decoded[0][5]],
            }
    except Exception as e:
        print(f"Failed to decode DVN config: {e}")
        return None # type: ignore


def get_current_config(
    endpoint, oapp: str, lib: str, eid: int, config_type: int):
    """Fetch current DVN configuration from chain"""
    try:
        config_bytes = endpoint.getConfig(oapp, lib, eid, config_type)
        if config_type == CONFIG_TYPE_READ:
            return decode_dvn_config(config_bytes, "read")
        elif config_type == CONFIG_TYPE_EXECUTOR:
            return decode_dvn_config(config_bytes, "executor")
        else:
            return decode_dvn_config(config_bytes, "uln")
    except Exception as e:
        print(f"Failed to get config: {e}")
        return None




def account_load(fname):
    path = os.path.expanduser(os.path.join("~", ".brownie", "accounts", fname + ".json"))
    with open(path, "r") as f:
        pkey = account.decode_keyfile_json(json.load(f), getpass())
        return account.Account.from_key(pkey)

lz = LZMetadata()

chains = ['ethereum', 'arbitrum', 'optimism', 'fraxtal']
lz_data = {chain: lz.get_chain_metadata(chain) for chain in chains}

with vote(
    OWNERSHIP,
    "[FastBridge] Update LayerZero DVN parameters to more conservative.",
    # live_env=CustomEnv(rpc=RPC_URL, account=account_load("curve")),
):
    cur_config = get_current_config(endpoint, "0x15945526b5C32D963391343e9Bc080838fe3e6d9", lz_data['ethereum']['metadata']['receiveUln302'], 30110, 2)
    print(f"[L1 ARB] Current config: {cur_config}")
    # Arbitrum
    endpoint.setConfig(
        "0x15945526b5C32D963391343e9Bc080838fe3e6d9",  # oapp
        "0xc02Ab410f0734EFa3F14628780e6e695156024C2",  # ReceiveUln302 lib
        [
            (
                30110,  # eid
                2,  # configType (ULN for send/receive)
                get_config(3600, l1_dvns),  # config
            )
        ]
    )
    upd_config = get_current_config(endpoint, "0x15945526b5C32D963391343e9Bc080838fe3e6d9", lz_data['ethereum']['metadata']['receiveUln302'], 30110, 2)
    print(f"[L1 ARB] Updated config: {upd_config}")
    ARB_RPC = f"https://lb.drpc.org/arbitrum/{DRPC_KEY}"
    with xvote(ARBITRUM, rpc=ARB_RPC):
        l2_endpoint = boa.from_etherscan("0x1a44076050125825900e736c501f859c50fE728c", api_key=ETHERSCAN_API_KEY)
        cur_config = get_current_config(l2_endpoint, "0x14e11C1B8F04A7dE306a7B5bf21bbca0D5cF79ff", lz_data['arbitrum']['metadata']['sendUln302'], 30101, 2)
        print(f"[L2 ARB] Current config: {cur_config}")
        l2_endpoint.setConfig(
            "0x14e11C1B8F04A7dE306a7B5bf21bbca0D5cF79ff",  # oapp
            "0x975bcD720be66659e3EB3C0e4F1866a3020E493A",  # SendUln302 lib
            [
                (
                    30101,  # eid
                    2,  # configType (ULN for send/receive)
                    get_config(
                        3600,
                        [
                            "0x2f55c492897526677c5b68fb199ea31e2c126416",  # LayerZero Labs
                            "0x4066b6e7bfd761b579902e7e8d03f4feb9b9536e",  # Swiss Stake
                        ],
                    ),  # config
                )
            ]
        )
        upd_config = get_current_config(l2_endpoint, "0x14e11C1B8F04A7dE306a7B5bf21bbca0D5cF79ff", lz_data['arbitrum']['metadata']['sendUln302'], 30101, 2)
        print(f"[L2 ARB] Updated config: {upd_config}")

    # Optimism
    vault_messenger = boa.from_etherscan("0x4A10d0FF9e394f3A3dCdb297973Db40Ce304b44f", api_key=ETHERSCAN_API_KEY)
    vault_messenger.setPeer(30111, Web3.to_bytes(hexstr="0x7a1f2f99B65f6c3B2413648c86C0326CfF8D8837"))  # New L2Messenger
    cur_config = get_current_config(endpoint, vault_messenger, lz_data['ethereum']['metadata']['receiveUln302'], 30111, 2)
    print(f"[L1 OPT] Current config: {cur_config}")
    endpoint.setConfig(
        vault_messenger,  # oapp
        "0xc02Ab410f0734EFa3F14628780e6e695156024C2",  # ReceiveUln302 lib
        [
            (
                30111,  # eid
                2,  # configType (ULN for send/receive)
                get_config(450, l1_dvns),  # config
            )
        ]
    )
    upd_config = get_current_config(endpoint, vault_messenger, lz_data['ethereum']['metadata']['receiveUln302'], 30111, 2)
    print(f"[L1 OPT] Updated config: {upd_config}")
    # Fraxtal
    cur_config = get_current_config(endpoint, "0xEC0e1c5Cc900D87b1FA44584310C43f82F75870F", lz_data['ethereum']['metadata']['receiveUln302'], 30255, 2)
    print(f"[L1 FRAX] Current config: {cur_config}")
    endpoint.setConfig(
        "0xEC0e1c5Cc900D87b1FA44584310C43f82F75870F",  # oapp
        "0xc02Ab410f0734EFa3F14628780e6e695156024C2",  # ReceiveUln302 lib
        [
            (
                30255,  # eid
                2,  # configType (ULN for send/receive)
                get_config(450, l1_dvns),  # config
            )
        ]
    )
    upd_config = get_current_config(endpoint, "0xEC0e1c5Cc900D87b1FA44584310C43f82F75870F", lz_data['ethereum']['metadata']['receiveUln302'], 30255, 2)
    print(f"[L1 FRAX] Updated config: {upd_config}")
    FRAX_RPC = f"https://lb.drpc.org/fraxtal/{DRPC_KEY}"
    with xvote(FRAXTAL, rpc=FRAX_RPC):
        l2_endpoint = boa.from_etherscan("0x1a44076050125825900e736c501f859c50fE728c", api_key=ETHERSCAN_API_KEY)
        cur_config = get_current_config(l2_endpoint, "0x672C38258729060bF443BA28FaEF4F2db154C6fC", lz_data['fraxtal']['metadata']['sendUln302'], 30101, 2)
        print(f"[L2 FRAX] Current config: {cur_config}")
        l2_endpoint.setConfig(
            "0x672C38258729060bF443BA28FaEF4F2db154C6fC",  # oapp
            "0x377530cdA84DFb2673bF4d145DCF0C4D7fdcB5b6",  # SendUln302 lib
            [
                (
                    30101,  # eid
                    2,  # configType (ULN for send/receive)
                    get_config(
                        450,
                        [
                            "0xcce466a522984415bc91338c232d98869193d46e",  # LayerZero Labs
                            "0x05df4949f0b4dc4c4b1adc0e01700bc669e935c3",  # Swiss Stake
                        ],
                    ),  # config
                )
            ]
        )
        upd_config = get_current_config(l2_endpoint, "0x672C38258729060bF443BA28FaEF4F2db154C6fC", lz_data['fraxtal']['metadata']['sendUln302'], 30101, 2)
        print(f"[L2 FRAX] Updated config: {upd_config}")