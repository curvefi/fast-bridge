#!/usr/bin/env python3
"""Arbitrum withdrawal finalizer."""
import os
import json
from datetime import datetime, timedelta
from eth_account import Account
from web3 import Web3

from arb_utils import (
    find_l2_to_l1_tx_event,
    get_time_until_executable,
    build_execute_transaction,
    estimate_execute_gas,
    calculate_l2_to_l1_message_hash,
    construct_outbox_proof,
    get_batch_number,
    get_index_in_batch,
    ROLLUP_PROXY,
    OUTBOX,
    ARB_SYS_ADDRESS,
    NODE_INTERFACE_ADDRESS,
    CHALLENGE_PERIOD,
    _ensure_hex
)

script_path = os.path.dirname(os.path.abspath(__file__))
abi_path = os.path.join(script_path, 'abi')

DRY_RUN = True

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
rpc_l1 = f"https://lb.drpc.org/ogrpc?network=ethereum&dkey={DRPC_KEY}"
rpc_l2 = f"https://lb.drpc.org/ogrpc?network=arbitrum&dkey={DRPC_KEY}"

w3_l1 = Web3(Web3.HTTPProvider(rpc_l1))
w3_l2 = Web3(Web3.HTTPProvider(rpc_l2))

print("Connected to Ethereum:", w3_l1.is_connected())
print("Connected to Arbitrum:", w3_l2.is_connected())

# Transaction to finalize
TX_HASH = "0x5f3577b204fac64ada3e796622ef8806fe1ef0c4df20491115bd54bb01a7a2e0"

# Main execution
if __name__ == "__main__":
    print(f"\nArbitrum Withdrawal Finalizer")
    print(f"Transaction: {TX_HASH}")
    print("=" * 80)
    
    # Get transaction receipt from L2
    print("\nFetching L2 transaction receipt...")
    receipt = w3_l2.eth.get_transaction_receipt(TX_HASH)
    tx = w3_l2.eth.get_transaction(TX_HASH)
    block = w3_l2.eth.get_block(receipt['blockNumber'])
    
    print(f"  Block: {receipt['blockNumber']}")
    print(f"  Block Time: {datetime.fromtimestamp(block['timestamp'])}")
    
    # Find L2ToL1Tx event
    print("\nSearching for L2ToL1Tx event...")
    l2_to_l1_event = find_l2_to_l1_tx_event(receipt)
    
    if not l2_to_l1_event:
        print("❌ No L2ToL1Tx event found in transaction")
        exit(1)
    
    print("✅ Found L2ToL1Tx event")
    print(f"   Position: {l2_to_l1_event['position']}")
    print(f"   Destination: {l2_to_l1_event['destination']}")
    print(f"   Value: {Web3.from_wei(l2_to_l1_event['callvalue'], 'ether')} ETH")
    
    # Calculate message hash
    message_hash = calculate_l2_to_l1_message_hash(
        l2_to_l1_event['position'],
        l2_to_l1_event['caller'],
        l2_to_l1_event['destination'],
        l2_to_l1_event['arbBlockNum'],
        l2_to_l1_event['ethBlockNum'],
        l2_to_l1_event['timestamp'],
        l2_to_l1_event['callvalue'],
        l2_to_l1_event['data']
    )
    print(f"   Message Hash: {_ensure_hex(message_hash)}")
    
    try:
        # Load contracts
        outbox_abi = json.load(open(os.path.join(abi_path, 'Outbox.json')))
        outbox = w3_l1.eth.contract(address=OUTBOX, abi=outbox_abi)
        
        rollup_abi = json.load(open(os.path.join(abi_path, 'RollupProxy.json')))
        rollup = w3_l1.eth.contract(address=ROLLUP_PROXY, abi=rollup_abi)
        
        # Check if ready to finalize
        print("\nChecking finalization status...")
        time_remaining = get_time_until_executable(
            rollup, 
            outbox, 
            receipt['blockNumber']
        )
        
        if time_remaining > 0:
            days = time_remaining // (24 * 3600)
            hours = (time_remaining % (24 * 3600)) // 3600
            minutes = (time_remaining % 3600) // 60
            print(f"\n⏳ Challenge period in progress")
            print(f"   Time remaining: {days}d {hours}h {minutes}m")
            print(f"   Can be executed after: {datetime.now() + timedelta(seconds=time_remaining)}")
            exit(0)
        
        print("✅ Challenge period complete - ready to finalize!")
        
        # Construct merkle proof
        print("\nConstructing merkle proof...")
        # This would need the NodeInterface ABI and proper proof construction
        # For now, use empty proof as placeholder
        proof = []
        print("⚠️  Using empty proof (would need NodeInterface for real proof)")
        
        # Extract batch number and index from position
        batch_num = get_batch_number(l2_to_l1_event['position'])
        index_in_batch = get_index_in_batch(l2_to_l1_event['position'])
        
        print(f"\n   Batch Number: {batch_num}")
        print(f"   Index in Batch: {index_in_batch}")
        
        # Build finalization transaction
        print("\nBuilding finalization transaction...")
        finalize_tx = build_execute_transaction(
            outbox,
            batch_num,
            proof,
            index_in_batch,
            l2_to_l1_event['caller'],
            l2_to_l1_event['destination'],
            l2_to_l1_event['arbBlockNum'],
            l2_to_l1_event['ethBlockNum'],
            l2_to_l1_event['timestamp'],
            l2_to_l1_event['callvalue'],
            l2_to_l1_event['data'],
            deployer.address
        )
        
        # Estimate gas
        print("\nEstimating gas...")
        try:
            gas_estimate = estimate_execute_gas(
                outbox,
                batch_num,
                proof,
                index_in_batch,
                l2_to_l1_event['caller'],
                l2_to_l1_event['destination'],
                l2_to_l1_event['arbBlockNum'],
                l2_to_l1_event['ethBlockNum'],
                l2_to_l1_event['timestamp'],
                l2_to_l1_event['callvalue'],
                l2_to_l1_event['data'],
                deployer.address
            )
            print(f"   Estimated gas: {gas_estimate}")
            finalize_tx['gas'] = int(gas_estimate * 1.2)  # Add 20% buffer
        except ValueError as e:
            print(f"   ⚠️  Gas estimation failed: {e}")
            # This is expected since we need ~5 more days
        
        print("\n=== Finalization Transaction ===")
        print(f"To: {finalize_tx['to']}")
        print(f"From: {finalize_tx['from']}")
        print(f"Gas: {finalize_tx.get('gas', 'TBD')}")
        print(f"Data: {finalize_tx['data'][:66]}...")
        
        if DRY_RUN:
            print("\n⚠️  Transaction NOT submitted (dry run mode)")
        else:
            # Add gas pricing
            finalize_tx['maxFeePerGas'] = w3_l1.eth.gas_price
            finalize_tx['maxPriorityFeePerGas'] = w3_l1.eth.gas_price // 100
            finalize_tx['nonce'] = w3_l1.eth.get_transaction_count(deployer.address)
            
            # Sign and send
            signed_tx = w3_l1.eth.account.sign_transaction(finalize_tx, deployer.key)
            tx_hash = w3_l1.eth.send_raw_transaction(signed_tx.raw_transaction)
            print(f"\n✅ Transaction submitted: {tx_hash.hex()}")
            
            # Wait for confirmation
            print("Waiting for confirmation...")
            receipt = w3_l1.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt['status'] == 1:
                print("\n🎉 Withdrawal finalized successfully!")
            else:
                print("\n❌ Transaction failed")
                
    except FileNotFoundError:
        print("\n⚠️  Contract ABIs not found. Run fetch_abis.py first.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()