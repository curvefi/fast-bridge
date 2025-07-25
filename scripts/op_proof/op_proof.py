#!/usr/bin/env python3
"""Optimism withdrawal proof builder."""
import os
import json
from eth_account import Account
from web3 import Web3
import time

from op_proof_utils import (
    find_corresponding_game,
    get_withdrawal_proof,
    build_output_root_proof,
    build_withdrawal_transaction,
    build_prove_transaction,
    estimate_prove_gas,
    get_withdrawal_hash_storage_slot,
)

DRY_RUN = True

script_path = os.path.dirname(os.path.abspath(__file__))
abi_path = os.path.join(script_path, 'abi')

# Load environment variables
DRPC_KEY = os.getenv("DRPC_API_KEY")
private_key = os.getenv("WEB3_TESTNET_PK")

if not DRPC_KEY:
    raise ValueError("DRPC_API_KEY not found in environment")
if not private_key:
    raise ValueError("WEB3_TESTNET_PK not found in environment")

# Setup account
deployer = Account.from_key(private_key)

# Setup RPC connections
rpc_l1 = f"https://lb.drpc.org/ethereum/{DRPC_KEY}"
rpc_l2 = f"https://lb.drpc.org/optimism/{DRPC_KEY}"

w3_l1 = Web3(Web3.HTTPProvider(rpc_l1))
w3_l2 = Web3(Web3.HTTPProvider(rpc_l2))

# Load L2ToL1MessagePasser on L2
message_passer_address = '0x4200000000000000000000000000000000000016'
message_passer_abi = json.load(open(os.path.join(abi_path, 'L2MessagePasser.json')))
message_passer = w3_l2.eth.contract(address=message_passer_address, abi=message_passer_abi)

# Load OptimismPortal on L1
portal_address = '0xbEb5Fc579115071764c7423A4f12eDde41f106Ed'
portal_abi = json.load(open(os.path.join(abi_path, 'L1Portal.json')))
portal = w3_l1.eth.contract(address=portal_address, abi=portal_abi)

# Load L1DisputeGameFactory on L1
dispute_game_factory_address = '0xe5965Ab5962eDc7477C8520243A95517CD252fA9'
dispute_game_factory_abi = json.load(open(os.path.join(abi_path, 'L1DisputeGameFactory.json')))
dispute_game_factory = w3_l1.eth.contract(address=dispute_game_factory_address, abi=dispute_game_factory_abi)

# Load L1AnchorStateRegistry on L1
anchor_state_registry_address = '0x23B2C62946350F4246f9f9D027e071f0264FD113'
anchor_state_registry_abi = json.load(open(os.path.join(abi_path, 'L1AnchorStateRegistry.json')))
anchor_state_registry = w3_l1.eth.contract(address=anchor_state_registry_address, abi=anchor_state_registry_abi)

# Get transaction receipt from L2
tx_hash = '0x91ae0d834c48c79e207ec185a53d6710fbf4ab0f190978147190ae97f6b3cd02'
receipt = w3_l2.eth.get_transaction_receipt(tx_hash)

# Find and decode MessagePassed event
message_passed_log = [
    log for log in receipt.logs 
    if log.address.lower() == message_passer_address.lower()
][0]
decoded = message_passer.events.MessagePassed().process_log(message_passed_log)

withdrawal_hash = decoded['args']['withdrawalHash']
print(f"Withdrawal Hash: {withdrawal_hash.hex()}")

# Find corresponding game for the withdrawal
print("\nFinding corresponding dispute game...")
# Try with just recent games first
analysis = find_corresponding_game(
    dispute_game_factory, 
    portal, 
    anchor_state_registry,
    receipt['blockNumber'], 
)

if not analysis['can_prove']:
    print("\n❌ Withdrawal cannot be proven yet")
    print(f"Your withdrawal block: {receipt['blockNumber']}")
    
    if analysis.get('recent_games'):
        print("\nRecent dispute games:")
        for i, game in enumerate(analysis['recent_games']):
            mins_ago = (time.time() - game['timestamp']) // 60
            print(f"  Game {i+1}: L2 block {game['l2BlockNumber']} ({mins_ago} minutes ago)")
    
    print("\n⏳ Wait a bit for a new game to be created")
    exit(1)

print("✅ Withdrawal can be proven!")

game = analysis['game']
print(f"\nFound optimal game:")
print(f"  Game index: {game['index']}")
print(f"  Game L2 block: {game['l2BlockNumber']}")
print(f"  Blocks ahead of withdrawal: {game['l2BlockNumber'] - receipt['blockNumber']}")

# Use the game's L2 block number for proofs 
game_l2_block_number = game['l2BlockNumber']

# Get withdrawal proof from L2 at the GAME's L2 block 
withdrawal_proof = get_withdrawal_proof(w3_l2, withdrawal_hash, game_l2_block_number)

# Get storage hash for output root proof at the GAME's L2 block
storage_slot = get_withdrawal_hash_storage_slot(withdrawal_hash)
proof_response = w3_l2.manager.request_blocking(
    "eth_getProof",
    [message_passer_address, [f"0x{storage_slot.hex()}"], hex(game_l2_block_number)]
)
storage_hash = proof_response['storageHash']

# Build output root proof using the GAME's L2 block
output_root_proof = build_output_root_proof(w3_l2, game_l2_block_number, storage_hash)

# Build withdrawal transaction
withdrawal_tx = build_withdrawal_transaction(decoded['args'])

# Print proof details
print("\n=== Withdrawal Proof ===")
print(f"L2 Block Number: {receipt['blockNumber']}")
print(f"L2 Output Index: {game['index']}")
print("\nWithdrawal Transaction:")
print(f"  Nonce: {withdrawal_tx[0]}")
print(f"  Sender: {withdrawal_tx[1]}")
print(f"  Target: {withdrawal_tx[2]}")
print(f"  Value: {withdrawal_tx[3]}")
print(f"  Gas Limit: {withdrawal_tx[4]}")
print(f"  Data: {withdrawal_tx[5].hex() if withdrawal_tx[5] else '0x'}")
print("\nGame Info:")
print(f"  Game L2 Block: {game_l2_block_number}")
print("\nOutput Root Proof (at game L2 block):")
print(f"  Version: {output_root_proof['version']}")
print(f"  State Root: {output_root_proof['stateRoot']}")
print(f"  Message Passer Storage Root: {output_root_proof['messagePasserStorageRoot']}")
print(f"  Latest Block Hash: {output_root_proof['latestBlockhash']}")
print(f"\nWithdrawal Proof: {len(withdrawal_proof)} nodes")

# Build proof transaction
try:
    tx = build_prove_transaction(
        portal,
        withdrawal_tx,
        game['index'],
        output_root_proof,
        withdrawal_proof,
        deployer.address
        )
    
    # Estimate gas
    try:
        gas_estimate = estimate_prove_gas(
            portal,
            withdrawal_tx,
            game['index'],
            output_root_proof,
            withdrawal_proof,
            deployer.address
        )
        print(f"\nEstimated gas: {gas_estimate}")
    except ValueError as ge:
        print(f"\n⚠️  {ge}")
        gas_estimate = None
    
    print("\n✅ Proof transaction built successfully!")
    if DRY_RUN:
        print("⚠️  Transaction NOT submitted (dry run mode)")
    else:
        tx['maxFeePerGas'] = w3_l1.eth.gas_price
        tx['maxPriorityFeePerGas'] = w3_l1.eth.gas_price//100
        tx['nonce'] = w3_l1.eth.get_transaction_count(deployer.address)
        signed_tx = w3_l1.eth.account.sign_transaction(tx, deployer.key)
        tx_hash = w3_l1.eth.send_raw_transaction(signed_tx.raw_transaction)
        print(f"Transaction submitted: {tx_hash.hex()}")
except Exception as e:
    print(f"\n❌ Error building proof transaction: {e}")
    import traceback
    traceback.print_exc()