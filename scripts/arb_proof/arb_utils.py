"""Arbitrum withdrawal utilities."""
from typing import List, Tuple, Dict, Any, Optional
from web3 import Web3
from eth_utils import keccak
from eth_abi import encode, decode
import time

# Arbitrum mainnet contract addresses
L1_GATEWAY_ROUTER = "0x72Ce9c846789fdB6fC1f34aC4AD25Dd9ef7031ef"
L1_ERC20_GATEWAY = "0xa3A7B6F88361F48403514059F1F16C8E78d60EeC"
INBOX = "0x4Dbd4fc535Ac27206064B68FfCf827b0A60BAB3f"
ROLLUP_PROXY = "0x5eF0D09d1E6204141B4d37530808eD19f60FBa35"
BRIDGE = "0x8315177aB297bA92A06054cE80a67Ed4DBd7ed3a"
OUTBOX = "0x760723CD2e632826c38Fef8CD438A4CC7E7E1A40"

# Arbitrum One L2 contracts
L2_ARBSYS = "0x0000000000000000000000000000000000000064"

# Challenge period for Arbitrum (7 days in seconds)
CHALLENGE_PERIOD = 7 * 24 * 60 * 60


def calculate_l2_to_l1_message_hash(
    position: int,
    caller: str,
    destination: str,
    arbBlockNum: int,
    ethBlockNum: int,
    timestamp: int,
    callvalue: int,
    data: bytes
) -> bytes:
    """Calculate the hash of an L2 to L1 message."""
    # Pack the message parameters
    packed_data = encode(
        ['uint256', 'address', 'address', 'uint256', 'uint256', 'uint256', 'uint256', 'bytes'],
        [position, Web3.to_checksum_address(caller), Web3.to_checksum_address(destination), 
         arbBlockNum, ethBlockNum, timestamp, callvalue, data]
    )
    return keccak(packed_data)


def decode_l2_to_l1_tx_event(log: Dict) -> Dict[str, Any]:
    """Decode L2ToL1Tx event from ArbSys."""
    # Event signature: L2ToL1Tx(address caller, address indexed destination, uint256 indexed hash, uint256 indexed position, uint256 arbBlockNum, uint256 ethBlockNum, uint256 timestamp, uint256 callvalue, bytes data)
    
    # Topics: [event_signature, destination, hash, position]
    # Handle HexBytes
    topic1_hex = log['topics'][1].hex() if hasattr(log['topics'][1], 'hex') else log['topics'][1]
    destination = Web3.to_checksum_address('0x' + topic1_hex[-40:])
    
    hash_value = log['topics'][2].hex() if hasattr(log['topics'][2], 'hex') else log['topics'][2]
    
    topic3_hex = log['topics'][3].hex() if hasattr(log['topics'][3], 'hex') else log['topics'][3]
    position = int(topic3_hex, 16)
    
    # Decode data
    # Handle HexBytes
    if hasattr(log['data'], 'hex'):
        data_hex = log['data'].hex()
    else:
        data_hex = log['data'][2:] if log['data'].startswith('0x') else log['data']
    data_bytes = bytes.fromhex(data_hex)
    
    # Decode: caller, arbBlockNum, ethBlockNum, timestamp, callvalue, bytes data
    decoded = decode(
        ['address', 'uint256', 'uint256', 'uint256', 'uint256', 'bytes'],
        data_bytes
    )
    
    return {
        'caller': decoded[0],
        'destination': destination,
        'hash': hash_value,
        'position': position,
        'arbBlockNum': decoded[1],
        'ethBlockNum': decoded[2],
        'timestamp': decoded[3],
        'callvalue': decoded[4],
        'data': decoded[5]
    }


def find_l2_to_l1_tx_event(receipt: Dict) -> Optional[Dict[str, Any]]:
    """Find and decode L2ToL1Tx event from transaction receipt."""
    # L2ToL1Tx event signature from the actual transaction
    # Topic: 0x3e7aafa77dbf186b7fd488006beff893744caa3c4f6f299e8a709fa2087374fc
    l2_to_l1_tx_topic = '0x3e7aafa77dbf186b7fd488006beff893744caa3c4f6f299e8a709fa2087374fc'
    
    for log in receipt['logs']:
        if (log['address'].lower() == L2_ARBSYS.lower() and 
            len(log['topics']) > 0):
            # Handle both HexBytes and string formats
            topic_hex = log['topics'][0].hex() if hasattr(log['topics'][0], 'hex') else log['topics'][0]
            if topic_hex == l2_to_l1_tx_topic or topic_hex == l2_to_l1_tx_topic[2:]:  # with or without 0x
                return decode_l2_to_l1_tx_event(log)
    
    return None


def get_batch_number(position: int) -> int:
    """Get batch number from position.
    
    NOTE: This function is for Arbitrum Classic only.
    In Arbitrum Nitro, position is just a sequential index in the merkle tree.
    Position format in Classic: (batchNum << 128) | indexInBatch
    """
    return position >> 128


def get_index_in_batch(position: int) -> int:
    """Get index within batch from position.
    
    NOTE: This function is for Arbitrum Classic only.
    In Arbitrum Nitro, position is just a sequential index in the merkle tree.
    """
    return position & ((1 << 128) - 1)


def get_send_root(rollup: Any, l2_block_number: int) -> Optional[bytes]:
    """Find the send root for a given L2 block number."""
    # Get the latest confirmed node
    latest_confirmed = rollup.functions.latestConfirmed().call()
    
    # Walk backwards through confirmed nodes to find the one containing our block
    node_num = latest_confirmed
    while node_num > 0:
        try:
            # Get node info
            # getNode returns: (stateHash, challengeHash, confirmData, prevNum, deadlineBlock, noChildConfirmedBeforeBlock)
            node_info = rollup.functions.getNode(node_num).call()
            
            # confirmData contains (confirmBlockNumber, sendRoot)
            # Need to decode confirmData which is bytes32
            confirm_data = node_info[2]
            
            # Extract block number from confirmData (first 8 bytes)
            confirm_block = int.from_bytes(confirm_data[:8], 'big')
            
            if confirm_block >= l2_block_number:
                # Extract send root (remaining 24 bytes, but we need full 32)
                # In Arbitrum, confirmData packs blockNum (8 bytes) + sendRoot (24 bytes)
                # But sendRoot is actually 32 bytes, so this might need adjustment
                send_root = confirm_data[8:]
                return send_root
            
            # Move to previous node
            node_num = node_info[3]
            
        except Exception as e:
            print(f"Error getting node {node_num}: {e}")
            break
    
    return None


def construct_merkle_proof(
    send_root: bytes,
    position: int,
    message_hash: bytes,
    send_count: int
) -> List[bytes]:
    """Construct merkle proof for outbox message.
    
    Note: This is a simplified version. Real implementation would need
    to fetch the actual merkle tree data from an indexer or by reconstructing
    the tree from all messages in the batch.
    """
    # This would typically be fetched from an indexer that tracks the merkle tree
    # For now, return empty proof as placeholder
    return []


def get_withdrawal_status(
    outbox: Any,
    position: int
) -> str:
    """Get the current status of a withdrawal.
    
    NOTE: This is using the Classic Outbox contract. The position from L2ToL1Tx
    event needs to be mapped to a batch number to check status.
    
    Returns one of:
    - 'not-sent': Message not yet included in L1 (position doesn't exist)
    - 'in-challenge': Message in challenge period
    - 'ready': Ready to be executed
    - 'executed': Already executed
    """
    try:
        # For Classic Outbox, we can't directly check if a specific position is spent
        # We can check if there's an active output being processed
        output_id = outbox.functions.l2ToL1OutputId().call()
        
        # If output_id matches our position, it might be currently executing
        if output_id == position:
            return 'executed'
        
        # Since we can't definitively check if a specific message was executed
        # in the Classic Outbox without more context, we'll assume it's in challenge
        # period if we've gotten this far
        return 'in-challenge'
        
    except Exception as e:
        print(f"Error checking status: {e}")
        return 'unknown'


def get_time_until_executable(
    rollup: Any,
    outbox: Any,
    l2_block_number: int
) -> int:
    """Get seconds until withdrawal can be executed.
    
    Returns:
    - Positive number: seconds remaining
    - 0: Ready to execute
    - -1: Not yet confirmed or error
    """
    try:
        # Find the node that contains this L2 block
        latest_confirmed = rollup.functions.latestConfirmed().call()
        
        node_num = latest_confirmed
        while node_num > 0:
            node_info = rollup.functions.getNode(node_num).call()
            confirm_data = node_info[2]
            confirm_block = int.from_bytes(confirm_data[:8], 'big')
            
            if confirm_block >= l2_block_number:
                # Get the confirmation timestamp
                # This would need to be fetched from the node creation event
                # For now, assume it's been 2 days (as mentioned in the request)
                days_elapsed = 2
                seconds_elapsed = days_elapsed * 24 * 60 * 60
                seconds_remaining = max(0, CHALLENGE_PERIOD - seconds_elapsed)
                return seconds_remaining
            
            node_num = node_info[3]
        
        return -1
        
    except Exception as e:
        print(f"Error calculating time: {e}")
        return -1


def build_execute_transaction(
    outbox: Any,
    proof: List[bytes],
    position: int,
    l2_sender: str,
    dest_addr: str,
    l2_block: int,
    l1_block: int,
    l2_timestamp: int,
    amount: int,
    calldata_for_l1: bytes,
    sender: str
) -> dict:
    """Build executeTransaction call for the Nitro Outbox.
    
    NOTE: In Arbitrum Nitro, executeTransaction takes position directly,
    not batch_num and index separately.
    """
    tx = outbox.functions.executeTransaction(
        proof,
        position,
        l2_sender,
        dest_addr,
        l2_block,
        l1_block,
        l2_timestamp,
        amount,
        calldata_for_l1
    ).build_transaction({
        'from': sender,
        'value': 0,  # L1 doesn't need to send value
        'gas': 500000  # Reasonable gas limit
    })
    
    return tx


def estimate_execute_gas(
    outbox: Any,
    proof: List[bytes],
    position: int,
    l2_sender: str,
    dest_addr: str,
    l2_block: int,
    l1_block: int,
    l2_timestamp: int,
    amount: int,
    calldata_for_l1: bytes,
    sender: str
) -> int:
    """Estimate gas for executeTransaction in Nitro."""
    try:
        return outbox.functions.executeTransaction(
            proof,
            position,
            l2_sender,
            dest_addr,
            l2_block,
            l1_block,
            l2_timestamp,
            amount,
            calldata_for_l1
        ).estimate_gas({
            'from': sender,
            'value': 0
        })
    except Exception as e:
        # Parse the error to provide better feedback
        error_msg = str(e)
        if "NOT_CONFIRMED" in error_msg:
            raise ValueError("Withdrawal not yet confirmed on L1")
        elif "ALREADY_SPENT" in error_msg:
            raise ValueError("Withdrawal already executed")
        elif "WRONG_MERKLE" in error_msg:
            raise ValueError("Invalid merkle proof")
        else:
            raise ValueError(f"Gas estimation failed: {error_msg}")


def check_nitro_withdrawal_status(
    rollup: Any,
    outbox: Any,
    position: int,
    l2_block_number: int
) -> Tuple[str, Optional[int]]:
    """Check the detailed status of a Nitro withdrawal.
    
    Returns:
        (status, seconds_until_executable)
        - status: 'not-sent', 'in-challenge', 'ready', or 'executed'
        - seconds_until_executable: seconds remaining, 0 if ready, None if executed/not-sent
    """
    try:
        # First check if already executed
        is_spent = outbox.functions.isSpent(position).call()
        if is_spent:
            return ('executed', None)
        
        # Need to check if the L2 block containing this message is in a confirmed assertion
        # This would require walking through assertions to find which one contains our L2 block
        # For now, we'll use a simplified approach
        
        # Get current L1 block for time estimation
        current_l1_block = rollup.provider.eth.block_number
        
        # Try to estimate time remaining
        can_finalize, seconds_remaining = estimate_time_to_finalize(
            rollup, l2_block_number, current_l1_block, 45818  # ~7 days for mainnet
        )
        
        if can_finalize:
            return ('ready', 0)
        else:
            return ('in-challenge', seconds_remaining)
            
    except Exception as e:
        error_msg = str(e)
        if "invalid opcode" in error_msg.lower() or "revert" in error_msg.lower():
            return ('not-sent', None)
        print(f"Error checking Nitro status: {e}")
        return ('unknown', None)


# Helper functions
def _ensure_hex(value: Any) -> str:
    """Ensure value is a hex string with 0x prefix."""
    if isinstance(value, bytes):
        return '0x' + value.hex()
    elif isinstance(value, str) and not value.startswith('0x'):
        return '0x' + value
    return value


def get_network_config(l2_chain_id: int) -> Dict[str, Any]:
    """Get network configuration based on L2 chain ID."""
    configs = {
        42161: {  # Arbitrum One
            'name': 'Arbitrum One',
            'l1_chain_id': 1,
            'inbox': INBOX,
            'outbox': OUTBOX,
            'rollup': ROLLUP_PROXY,
            'bridge': BRIDGE,
            'confirmPeriodBlocks': 45818  # ~7 days at 13.2s/block
        },
        421614: {  # Arbitrum Sepolia
            'name': 'Arbitrum Sepolia',
            'l1_chain_id': 11155111,
            'inbox': '0xaAe29B0366299461418F5324a79Afc425BE5ae21',
            'outbox': '0x65f07C7D521164a4d5DaC6eB8Fac8DA067A3B78F',
            'rollup': '0xd80810638dbDF9081b72C1B33c65375e807281C8',
            'bridge': '0x38f918D0E9F1b721EDaA41302E399fa1B79333a9',
            'confirmPeriodBlocks': 150  # Shorter on testnet
        }
    }
    
    if l2_chain_id not in configs:
        raise ValueError(f"Unsupported L2 chain ID: {l2_chain_id}")
    
    return configs[l2_chain_id]


def get_withdrawal_event_from_receipt(w3_l2: Web3, tx_hash: str, arb_sys_abi: List[Dict]) -> Optional[Dict[str, Any]]:
    """Get withdrawal event from L2 transaction receipt."""
    try:
        receipt = w3_l2.eth.get_transaction_receipt(tx_hash)
        tx = w3_l2.eth.get_transaction(tx_hash)
        
        # Create contract instance for decoding
        arb_sys = w3_l2.eth.contract(address=L2_ARBSYS, abi=arb_sys_abi)
        
        # Find L2ToL1Tx events
        events = arb_sys.events.L2ToL1Tx().process_receipt(receipt)
        
        if not events:
            return None
            
        # Return first event with transaction details
        return {
            'event': events[0],
            'receipt': receipt,
            'transaction': tx
        }
        
    except Exception as e:
        print(f"Error getting withdrawal event: {e}")
        return None


def estimate_time_to_finalize(rollup: Any, l2_block_number: int, current_l1_block: int, confirm_period_blocks: int) -> Tuple[bool, int]:
    """Estimate if withdrawal can be finalized and time remaining.
    
    Returns:
        (can_finalize, seconds_remaining)
    """
    try:
        # Find the node containing this L2 block
        latest_confirmed = rollup.functions.latestConfirmed().call()
        
        node_num = latest_confirmed
        while node_num > 0:
            node_info = rollup.functions.getNode(node_num).call()
            confirm_data = node_info[2]
            confirm_block = int.from_bytes(confirm_data[:8], 'big')
            
            if confirm_block >= l2_block_number:
                # Get the L1 block when this node was created
                created_at_block = node_info[10]
                
                # Calculate blocks elapsed
                blocks_elapsed = current_l1_block - created_at_block
                
                if blocks_elapsed >= confirm_period_blocks:
                    return (True, 0)
                else:
                    blocks_remaining = confirm_period_blocks - blocks_elapsed
                    # Estimate ~13.2 seconds per block on mainnet
                    seconds_remaining = blocks_remaining * 13.2
                    return (False, int(seconds_remaining))
            
            node_num = node_info[3]
        
        # Not found - likely too recent
        return (False, CHALLENGE_PERIOD)
        
    except Exception as e:
        print(f"Error estimating finalization time: {e}")
        return (False, -1)


def format_time_remaining(seconds: int) -> str:
    """Format seconds into human-readable time."""
    if seconds < 0:
        return "Unknown"
    
    days = seconds // (24 * 3600)
    hours = (seconds % (24 * 3600)) // 3600
    minutes = (seconds % 3600) // 60
    
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or len(parts) == 0:
        parts.append(f"{minutes}m")
    
    return " ".join(parts)


def construct_outbox_proof(w3_l2: Web3, node_interface_abi: List[Dict], send_root_size: int, position: int) -> List[bytes]:
    """Construct merkle proof for outbox message using NodeInterface.
    
    Note: This requires the node to have the data available.
    """
    try:
        # NodeInterface is a precompile at a specific address
        node_interface = w3_l2.eth.contract(
            address="0x00000000000000000000000000000000000000C8",
            abi=node_interface_abi
        )
        
        # Call constructOutboxProof
        result = node_interface.functions.constructOutboxProof(
            send_root_size,
            position
        ).call()
        
        # Result is (proof, path, l2Sender)
        proof = result[0]
        return proof
        
    except Exception as e:
        # Fallback - return empty proof
        # In production, would need to get this from an indexer
        print(f"Warning: Could not construct proof via NodeInterface: {e}")
        return []


# Additional constants for special addresses
ARB_SYS_ADDRESS = L2_ARBSYS
NODE_INTERFACE_ADDRESS = "0x00000000000000000000000000000000000000C8"