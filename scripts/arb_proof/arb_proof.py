#!/usr/bin/env python3
import os
import sys
import json
import warnings
from typing import Dict, Any, Tuple
from pathlib import Path
from eth_account import Account
from web3 import Web3

# Suppress ABI mismatch warnings from web3
warnings.filterwarnings("ignore", message=".*MismatchedABI.*")

# ============================================================================
# USER CONFIGURATION
# ============================================================================
TX_HASH = "0x5f3577b204fac64ada3e796622ef8806fe1ef0c4df20491115bd54bb01a7a2e0"
DRY_RUN = False  # Set to False to actually execute the transaction

# ============================================================================
# CONSTANTS
# ============================================================================
ROLLUP_PROXY = "0x5eF0D09d1E6204141B4d37530808eD19f60FBa35"  # Arbitrum One
ARBSYS = "0x0000000000000000000000000000000000000064"
NODE_INTERFACE = "0x00000000000000000000000000000000000000C8"

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def load_abi(name: str) -> list:
    """Load ABI from file."""
    abi_path = Path(__file__).parent / "abis" / f"{name}.json"
    with open(abi_path, 'r') as f:
        return json.load(f)


def get_providers() -> Tuple[Web3, Web3]:
    """Get L1 and L2 Web3 providers using DRPC."""
    key = os.getenv("DRPC_API_KEY")
    if not key:
        raise ValueError("DRPC_API_KEY not set in environment")
    
    l1 = Web3(Web3.HTTPProvider(f"https://lb.drpc.org/ogrpc?network=ethereum&dkey={key}"))
    l2 = Web3(Web3.HTTPProvider(f"https://lb.drpc.org/ogrpc?network=arbitrum&dkey={key}"))
    
    if not (l1.is_connected() and l2.is_connected()):
        raise RuntimeError("Cannot connect to L1/L2 networks")
    
    return l1, l2


def extract_size_from_receipt(receipt: Dict[str, Any]) -> Tuple[int, int]:
    """Extract the cumulative size from SendMerkleUpdate event in L2 receipt.
    
    Returns (size_raw_uint256, size64_effective).
    Nitro indexes all params, so size is in topics[3]. NodeInterface uses uint64."""
    TOPIC_SMU = Web3.keccak(text="SendMerkleUpdate(uint256,bytes32,uint256)").hex()
    arbsys = Web3.to_checksum_address(ARBSYS)
    size_raw = None
    
    for log in receipt["logs"]:
        # Check if it's from ArbSys
        if log["address"].lower() != arbsys.lower():
            continue
        
        # Check if it's SendMerkleUpdate event
        topic0 = log["topics"][0].hex() if hasattr(log["topics"][0], "hex") else log["topics"][0]
        if topic0 != TOPIC_SMU:
            continue
        
        # Nitro: all params indexed, read from topics[3]
        if len(log["topics"]) > 3:
            t3 = log["topics"][3]
            size_raw = int(t3.hex(), 16) if hasattr(t3, "hex") else int(t3, 16)
            # Keep the last/maximum if multiple events
    
    if size_raw is None:
        raise RuntimeError("SendMerkleUpdate not found in receipt")
    
    # NodeInterface uses uint64, so mask to 64 bits
    size64 = size_raw & ((1 << 64) - 1)
    return size_raw, size64


def parse_withdrawal_event(w3_l2: Web3, tx_hash: str) -> Dict[str, Any]:
    """Parse L2ToL1Tx event from withdrawal transaction."""
    receipt = w3_l2.eth.get_transaction_receipt(tx_hash)
    if not receipt:
        raise ValueError(f"Transaction {tx_hash} not found")
    
    # Parse L2ToL1Tx event
    arb_sys = w3_l2.eth.contract(address=ARBSYS, abi=load_abi("ArbSys"))
    events = arb_sys.events.L2ToL1Tx().process_receipt(receipt)
    
    if not events:
        raise ValueError("No L2ToL1Tx event found - not a withdrawal transaction")
    
    # For token withdrawals, prefer events going to known gateways
    GATEWAYS = {
        Web3.to_checksum_address("0xa3A7B6F88361F48403514059F1F16C8E78d60EeC"),  # L1 ERC20 Gateway
        Web3.to_checksum_address("0x72Ce9c846789fdB6fC1f34aC4AD25Dd9ef7031ef"),  # L1 Gateway Router
    }
    
    # Find event going to a gateway, or use first one
    event = next((e for e in events if Web3.to_checksum_address(e["args"]["destination"]) in GATEWAYS), events[0])
    
    # Normalize data to bytes
    calldata = event["args"]["data"]
    if isinstance(calldata, str):
        calldata = Web3.to_bytes(hexstr=calldata)
    
    return {
        "position": int(event["args"]["position"]),
        "caller": event["args"]["caller"],
        "destination": event["args"]["destination"],
        "arbBlockNum": int(event["args"]["arbBlockNum"]),
        "ethBlockNum": int(event["args"]["ethBlockNum"]),
        "timestamp": int(event["args"]["timestamp"]),
        "callvalue": int(event["args"]["callvalue"]),
        "data": calldata,
        "receipt": receipt
    }


def find_valid_size(w3_l1: Web3, w3_l2: Web3, outbox_addr: str, leaf: int) -> int:
    """Find a valid size by trying different values when SendMerkleUpdate has size=0."""
    outbox = w3_l1.eth.contract(address=Web3.to_checksum_address(outbox_addr), abi=load_abi("Outbox_impl"))
    
    # Try common size patterns
    size_attempts = [
        leaf + 1,  # Minimum size
        150000,    # Common size near this leaf
        200000,
        250000,
        300000,
        400000,
        500000
    ]
    
    for test_size in size_attempts:
        try:
            print(f"    Trying size {test_size}...")
            proof_data = build_proof(w3_l2, test_size, leaf)
            root = proof_data['root']
            
            # Check if this root is registered in the outbox
            l2_block_hash = outbox.functions.roots(root).call()
            if int.from_bytes(l2_block_hash, "big") != 0:
                print(f"    Found valid size: {test_size}")
                return test_size
        except Exception:
            continue
    
    return None


def build_proof(w3_l2: Web3, size: int, leaf: int) -> Dict[str, Any]:
    """Build merkle proof using NodeInterface."""
    node = w3_l2.eth.contract(address=NODE_INTERFACE, abi=load_abi("NodeInterface"))
    
    # NodeInterface uses uint64
    size64 = size & ((1 << 64) - 1)
    leaf64 = leaf & ((1 << 64) - 1)
    
    send, root, proof = node.functions.constructOutboxProof(size64, leaf64).call()
    
    return {
        "send": Web3.to_hex(send),
        "root": Web3.to_hex(root),
        "proof": [Web3.to_hex(p) for p in proof]
    }


def check_status(w3_l1: Web3, w3_l2: Web3, tx_hash: str) -> Dict[str, Any]:
    """Check withdrawal status and return detailed information."""
    print(f"\nChecking withdrawal: {tx_hash}")
    print("=" * 70)
    
    # Parse L2 withdrawal event
    print("\nParsing L2 transaction...")
    withdrawal = parse_withdrawal_event(w3_l2, tx_hash)
    leaf = withdrawal["position"]
    leaf64 = leaf & ((1 << 64) - 1)
    
    # Get outbox address first
    rollup = w3_l1.eth.contract(address=ROLLUP_PROXY, abi=load_abi("Rollup_impl"))
    outbox_addr = rollup.functions.outbox().call()
    
    # Extract size from receipt
    try:
        size_raw, size64 = extract_size_from_receipt(withdrawal["receipt"])
        print(f"  Leaf: {leaf} (leaf64={leaf64})")
        print(f"  Size(raw topic): {hex(size_raw)}")
        print(f"  Size(effective): {size64}")
    except RuntimeError as e:
        print(f"  WARNING: {e}")
        print("  Trying to find valid size...")
        size64 = find_valid_size(w3_l1, w3_l2, outbox_addr, leaf)
        if size64 is None:
            print("\nStatus: ERROR - Could not determine valid size")
            return {
                "status": "ERROR",
                "withdrawal": withdrawal,
                "proof_data": None,
                "outbox_addr": outbox_addr
            }
    
    # Nitro requirement: size64 >= leaf64 (not strictly greater)
    if size64 < leaf64:
        print(f"  ERROR: size64 ({size64}) must be >= leaf64 ({leaf64})")
        return {
            "status": "ERROR",
            "withdrawal": withdrawal,
            "proof_data": None,
            "outbox_addr": outbox_addr
        }
    
    print(f"  Value: {Web3.from_wei(withdrawal['callvalue'], 'ether')} ETH")
    print(f"  Destination: {withdrawal['destination']}")
    
    print(f"\nOutbox: {outbox_addr}")
    
    # Build proof with the uint64 values
    print("\nBuilding merkle proof...")
    proof_data = build_proof(w3_l2, size64, leaf64)
    root = proof_data["root"]
    print(f"  Root: {root}")
    print(f"  Send: {proof_data['send']}")
    
    # Check if root is posted on L1
    outbox = w3_l1.eth.contract(address=Web3.to_checksum_address(outbox_addr), abi=load_abi("Outbox_impl"))
    l2_block_hash = outbox.functions.roots(root).call()
    
    if int.from_bytes(l2_block_hash, "big") == 0:
        print("\nStatus: NOT_POSTED")
        print("  Root not in Outbox yet (unconfirmed or in challenge period)")
        return {
            "status": "NOT_POSTED",
            "withdrawal": withdrawal,
            "proof_data": proof_data,
            "outbox_addr": outbox_addr
        }
    
    print("  Root confirmed on L1")
    
    # Check if already spent (use leaf64 for consistency)
    already_spent = False
    try:
        already_spent = outbox.functions.isSpent(leaf64).call()
    except Exception as e:
        print(f"  Warning: Could not check isSpent: {e}")
    
    if already_spent:
        print("\nStatus: EXECUTED")
        print("  Withdrawal already finalized")
        status = "EXECUTED"
    else:
        # Try gas estimation to verify everything is correct
        try:
            # Convert proof to bytes
            proof_bytes = [Web3.to_bytes(hexstr=p) for p in proof_data["proof"]]
            
            gas = outbox.functions.executeTransaction(
                proof_bytes,
                leaf64,  # Use leaf64 for consistency
                withdrawal["caller"],
                withdrawal["destination"],
                withdrawal["arbBlockNum"],
                withdrawal["ethBlockNum"],
                withdrawal["timestamp"],
                withdrawal["callvalue"],
                withdrawal["data"]  # Already normalized to bytes
            ).estimate_gas({"from": "0x" + "0" * 40, "value": 0})
            
            print("\nStatus: READY TO EXECUTE")
            print(f"  Estimated gas: {gas}")
            status = "READY"
        except Exception as e:
            error_msg = str(e)
            print("\nStatus: ERROR")
            print(f"  Gas estimation failed: {error_msg}")
            
            # Try to provide helpful error messages
            if "WRONG_MERKLE" in error_msg or "invalid merkle" in error_msg.lower():
                print("  Issue: Proof/root/index mismatch")
            elif "NOT_CONFIRMED" in error_msg:
                print("  Issue: Entry not yet confirmed")
            
            status = "ERROR"
    
    return {
        "status": status,
        "withdrawal": withdrawal,
        "proof_data": proof_data,
        "outbox_addr": outbox_addr,
        "size64": size64,
        "leaf64": leaf64
    }


def execute_withdrawal(w3_l1: Web3, status_data: Dict[str, Any]) -> bool:
    """Execute a ready withdrawal."""
    if status_data["status"] != "READY":
        print(f"\nCannot execute: status is {status_data['status']}")
        return False
    
    # Get signer
    pk = os.getenv("WEB3_TESTNET_PK")
    if not pk:
        raise ValueError("WEB3_TESTNET_PK not set")
    
    account = Account.from_key(pk)
    print("\nPreparing withdrawal execution")
    print(f"  Signer: {account.address}")
    
    # Build transaction
    outbox = w3_l1.eth.contract(address=status_data["outbox_addr"], abi=load_abi("Outbox_impl"))
    withdrawal = status_data["withdrawal"]
    
    # Convert proof to bytes
    proof_bytes = [Web3.to_bytes(hexstr=p) for p in status_data["proof_data"]["proof"]]
    
    tx = outbox.functions.executeTransaction(
        proof_bytes,
        status_data["leaf64"],  # Use leaf64 for consistency
        withdrawal["caller"],
        withdrawal["destination"],
        withdrawal["arbBlockNum"],
        withdrawal["ethBlockNum"],
        withdrawal["timestamp"],
        withdrawal["callvalue"],
        withdrawal["data"]  # Already normalized to bytes
    ).build_transaction({
        "from": account.address,
        "value": 0,
        "gas": 600_000,
        "maxFeePerGas": w3_l1.eth.gas_price,
        "maxPriorityFeePerGas": w3_l1.eth.gas_price // 50,
        "nonce": w3_l1.eth.get_transaction_count(account.address),
        "chainId": 1  # Explicitly set mainnet chainId
    })
    
    print(f"  To: {tx['to']}")
    print(f"  Gas: {tx['gas']}")
    print(f"  Data: {tx['data'][:66]}...")
    
    # Ask for confirmation
    print("\n" + "=" * 70)
    response = input("Do you want to execute this transaction? (y/n): ")
    if response.lower() != 'y':
        print("Transaction cancelled")
        return False
    
    # Execute
    signed = w3_l1.eth.account.sign_transaction(tx, account.key)
    tx_hash = w3_l1.eth.send_raw_transaction(signed.raw_transaction)
    print(f"\nTransaction submitted: {tx_hash.hex()}")
    
    print("Waiting for confirmation...")
    receipt = w3_l1.eth.wait_for_transaction_receipt(tx_hash)
    
    if receipt["status"] == 1:
        print("\nWithdrawal executed successfully!")
        return True
    else:
        print("\nTransaction failed")
        return False


def main():
    try:
        # Get providers
        w3_l1, w3_l2 = get_providers()
        print("Connected to L1 and L2")
        
        # Check status
        status_data = check_status(w3_l1, w3_l2, TX_HASH)
        
        # Handle execution
        if DRY_RUN:
            print("\n" + "=" * 70)
            print("DRY RUN MODE - No transaction will be sent")
            if status_data["status"] == "READY":
                print("Withdrawal is ready to execute. Set DRY_RUN=False to execute.")
        else:
            if status_data["status"] == "READY":
                execute_withdrawal(w3_l1, status_data)
            else:
                print(f"\nWithdrawal not ready for execution (status: {status_data['status']})")
                
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())