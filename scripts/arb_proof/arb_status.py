#!/usr/bin/env python3
"""Arbitrum withdrawal status checker."""
import os
import json
from web3 import Web3
from datetime import datetime, timedelta

from arb_utils import (
    find_l2_to_l1_tx_event,
    get_withdrawal_status,
    get_time_until_executable,
    calculate_l2_to_l1_message_hash,
    ROLLUP_PROXY,
    OUTBOX,
    L2_ARBSYS,
    CHALLENGE_PERIOD,
    _ensure_hex
)

script_path = os.path.dirname(os.path.abspath(__file__))
abi_path = os.path.join(script_path, 'abi')

# Load environment variables
DRPC_KEY = os.getenv("DRPC_API_KEY")
if not DRPC_KEY:
    raise ValueError("DRPC_API_KEY not found in environment")

# Setup RPC connections
rpc_l1 = f"https://lb.drpc.org/ogrpc?network=ethereum&dkey={DRPC_KEY}"
rpc_l2 = f"https://lb.drpc.org/ogrpc?network=arbitrum&dkey={DRPC_KEY}"

w3_l1 = Web3(Web3.HTTPProvider(rpc_l1))
w3_l2 = Web3(Web3.HTTPProvider(rpc_l2))

print("Connected to Ethereum:", w3_l1.is_connected())
print("Connected to Arbitrum:", w3_l2.is_connected())

# Transaction to check
TX_HASH = "0x5f3577b204fac64ada3e796622ef8806fe1ef0c4df20491115bd54bb01a7a2e0"

# Main execution
if __name__ == "__main__":
    print(f"\nChecking Arbitrum withdrawal status for transaction: {TX_HASH}")
    print("=" * 80)
    
    # Get transaction receipt from L2
    print("\nFetching L2 transaction receipt...")
    receipt = w3_l2.eth.get_transaction_receipt(TX_HASH)
    
    # Get transaction details
    tx = w3_l2.eth.get_transaction(TX_HASH)
    block = w3_l2.eth.get_block(receipt['blockNumber'])
    
    print(f"  Block: {receipt['blockNumber']}")
    print(f"  Block Time: {datetime.fromtimestamp(block['timestamp'])}")
    print(f"  From: {tx['from']}")
    print(f"  Status: {'Success' if receipt['status'] == 1 else 'Failed'}")
    
    # Find L2ToL1Tx event
    print("\nSearching for L2ToL1Tx event...")
    l2_to_l1_event = find_l2_to_l1_tx_event(receipt)
    
    if not l2_to_l1_event:
        print("❌ No L2ToL1Tx event found in transaction")
        print("   This transaction does not appear to be an L2-to-L1 withdrawal")
        exit(1)
    
    print("✅ Found L2ToL1Tx event:")
    print(f"   Position: {l2_to_l1_event['position']}")
    print(f"   Caller: {l2_to_l1_event['caller']}")
    print(f"   Destination: {l2_to_l1_event['destination']}")
    print(f"   Value: {Web3.from_wei(l2_to_l1_event['callvalue'], 'ether')} ETH")
    print(f"   Arb Block: {l2_to_l1_event['arbBlockNum']}")
    print(f"   ETH Block: {l2_to_l1_event['ethBlockNum']}")
    
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
    
    # Load contracts (only if ABIs exist)
    try:
        # Load Outbox on L1
        outbox_abi = json.load(open(os.path.join(abi_path, 'Outbox.json')))
        outbox = w3_l1.eth.contract(address=OUTBOX, abi=outbox_abi)
        
        # Load RollupProxy on L1
        rollup_abi = json.load(open(os.path.join(abi_path, 'RollupProxy.json')))
        rollup = w3_l1.eth.contract(address=ROLLUP_PROXY, abi=rollup_abi)
        
        # Check withdrawal status
        print("\nChecking L1 status...")
        status = get_withdrawal_status(outbox, l2_to_l1_event['position'])
        
        print(f"\n📊 Withdrawal Status: {status.upper()}")
        
        if status == 'executed':
            print("   ✅ This withdrawal has already been executed!")
        
        elif status == 'in-challenge':
            # Calculate time remaining
            time_remaining = get_time_until_executable(
                rollup, 
                outbox, 
                receipt['blockNumber']
            )
            
            if time_remaining > 0:
                days = time_remaining // (24 * 3600)
                hours = (time_remaining % (24 * 3600)) // 3600
                minutes = (time_remaining % 3600) // 60
                
                print(f"   ⏳ Challenge period in progress")
                print(f"   Time remaining: {days}d {hours}h {minutes}m")
                print(f"   Can be executed after: {datetime.now() + timedelta(seconds=time_remaining)}")
            else:
                print("   ✅ Challenge period complete - ready to execute!")
        
        elif status == 'ready':
            print("   ✅ Ready to be executed!")
        
        elif status == 'not-sent':
            print("   ❌ Message not yet included on L1")
            print("   This might indicate the L2 block hasn't been posted to L1 yet")
        
        else:
            print(f"   ⚠️  Unknown status: {status}")
            
    except FileNotFoundError:
        print("\n⚠️  Contract ABIs not found. Run fetch_abis.py first to get full status info.")
        print("   Basic info from the event has been displayed above.")
    except Exception as e:
        print(f"\n❌ Error checking L1 status: {e}")
        import traceback
        traceback.print_exc()
    
    # Calculate expected finalization time
    print("\n📅 Timeline:")
    block_time = datetime.fromtimestamp(block['timestamp'])
    print(f"   Transaction time: {block_time}")
    print(f"   Challenge period: 7 days")
    expected_ready = block_time + timedelta(days=7)
    print(f"   Expected ready: {expected_ready}")
    
    time_since = datetime.now() - block_time
    print(f"   Time elapsed: {time_since.days}d {time_since.seconds//3600}h")
    
    if time_since.total_seconds() < CHALLENGE_PERIOD:
        time_left = CHALLENGE_PERIOD - time_since.total_seconds()
        days_left = int(time_left // (24 * 3600))
        hours_left = int((time_left % (24 * 3600)) // 3600)
        print(f"   Estimated time remaining: ~{days_left}d {hours_left}h")