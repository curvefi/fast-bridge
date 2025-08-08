#!/usr/bin/env python3
"""Optimism withdrawal finalizer."""
import os
import json
from eth_account import Account
from web3 import Web3

from op_proof_utils import (
    get_withdrawal_status,
    get_time_to_finalize,
    build_finalize_transaction,
    build_withdrawal_transaction
)

script_path = os.path.dirname(os.path.abspath(__file__))
abi_path = os.path.join(script_path, 'abi')

DRY_RUN = False

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

# Load OptimismPortal on L1
portal_address = '0xbEb5Fc579115071764c7423A4f12eDde41f106Ed'
portal_abi = json.load(open(os.path.join(abi_path, 'L1Portal.json')))
portal = w3_l1.eth.contract(address=portal_address, abi=portal_abi)

# Load L1AnchorStateRegistry on L1  
anchor_state_registry_address = '0x23B2C62946350F4246f9f9D027e071f0264FD113'
anchor_state_registry_abi = json.load(open(os.path.join(abi_path, 'L1AnchorStateRegistry.json')))
anchor_state_registry = w3_l1.eth.contract(address=anchor_state_registry_address, abi=anchor_state_registry_abi)


# Main execution
if __name__ == "__main__":
    # Get transaction receipt from L2
    tx_hash = '0x91ae0d834c48c79e207ec185a53d6710fbf4ab0f190978147190ae97f6b3cd02'
    receipt = w3_l2.eth.get_transaction_receipt(tx_hash)
    
    # Load L2ToL1MessagePasser on L2
    message_passer_address = '0x4200000000000000000000000000000000000016'
    message_passer_abi = json.load(open(os.path.join(abi_path, 'L2MessagePasser.json')))
    message_passer = w3_l2.eth.contract(address=message_passer_address, abi=message_passer_abi)
    
    # Find and decode MessagePassed event
    message_passed_log = [
        log for log in receipt.logs 
        if log.address.lower() == message_passer_address.lower()
    ][0]
    decoded = message_passer.events.MessagePassed().process_log(message_passed_log)
    
    withdrawal_hash = decoded['args']['withdrawalHash']
    print(f"Withdrawal Hash: {withdrawal_hash.hex()}")
    
    # Build withdrawal transaction tuple
    withdrawal_tx = build_withdrawal_transaction(decoded['args'])
    
    # Check withdrawal status
    print("\nChecking withdrawal status...")
    status = get_withdrawal_status(portal, anchor_state_registry, withdrawal_hash)
    print(f"Status: {status}")
    
    if status == 'waiting-to-prove':
        print("\n❌ Withdrawal has not been proven yet")
        print("Run op_proof.py first to prove the withdrawal")
        exit(1)
    elif status == 'ready-to-prove':
        print("\n❌ Withdrawal needs to be (re)proven")
        print("Run op_proof.py to prove the withdrawal")
        exit(1)
    elif status == 'finalized':
        print("\n✅ Withdrawal already finalized!")
        exit(0)
    elif status == 'waiting-to-finalize':
        seconds_remaining = get_time_to_finalize(portal, withdrawal_hash)
        if seconds_remaining > 0:
            hours = seconds_remaining // 3600
            minutes = (seconds_remaining % 3600) // 60
            print("\n⏳ Challenge period in progress")
            print(f"Time remaining: {hours}h {minutes}m")
            print("\nCome back later when the challenge period has passed")
            exit(0)
    
    # Ready to finalize
    print("\n✅ Withdrawal ready to finalize!")
    
    # Build finalization transaction
    try:
        tx = build_finalize_transaction(portal, withdrawal_tx, deployer.address)
        
        # Estimate gas
        try:
            gas_estimate = portal.functions.finalizeWithdrawalTransaction(
                withdrawal_tx
            ).estimate_gas({'from': deployer.address})
            print(f"\nEstimated gas: {gas_estimate}")
            tx['gas'] = int(gas_estimate * 1.2)  # Add 20% buffer
        except Exception as e:
            print(f"\n⚠️  Gas estimation failed: {e}")
        
        print("\n=== Finalization Transaction ===")
        print(f"To: {tx['to']}")
        print(f"From: {tx['from']}")
        print(f"Gas: {tx['gas']}")
        print(f"Data: {tx['data'][:66]}...")
        
        if DRY_RUN:
            print("\n⚠️  Transaction NOT submitted (dry run mode)")
        else:
            # Add gas pricing
            tx['maxFeePerGas'] = int(1.5*w3_l1.eth.gas_price)
            tx['maxPriorityFeePerGas'] = w3_l1.eth.gas_price // 100
            tx['nonce'] = w3_l1.eth.get_transaction_count(deployer.address)
            
            # Sign and send
            signed_tx = w3_l1.eth.account.sign_transaction(tx, deployer.key)
            tx_hash = w3_l1.eth.send_raw_transaction(signed_tx.raw_transaction)
            print(f"\n✅ Transaction submitted: {tx_hash.hex()}")
            
            # Wait for confirmation
            print("Waiting for confirmation...")
            receipt = w3_l1.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt['status'] == 1:
                print("\n🎉 Withdrawal finalized successfully!")
            else:
                print("\n❌ Transaction failed")
                
    except Exception as e:
        print(f"\n❌ Error building finalization transaction: {e}")
        import traceback
        traceback.print_exc()