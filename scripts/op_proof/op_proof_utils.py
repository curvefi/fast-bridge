"""Optimism withdrawal proof utilities."""
from typing import List, Tuple, Dict, Any
from web3 import Web3
from web3.exceptions import ContractCustomError
from eth_utils import keccak
from eth_abi import encode
import rlp


# Constants
L2_MESSAGE_PASSER = "0x4200000000000000000000000000000000000016"
ZERO_VERSION = "0x" + "00" * 32


def find_corresponding_game(
    dispute_game_factory: Any,
    portal: Any,
    anchor_state_registry: Any,
    l2_block_number: int,
    batch_size: int = 100
) -> Dict[str, Any]:
    """Find the optimal game for proving a withdrawal."""
    try:
        game_type = portal.functions.respectedGameType().call()
        total_games = dispute_game_factory.functions.gameCount().call()
        
        if total_games == 0:
            return {'can_prove': False, 'game': None, 'recent_games': []}
            
        # Get retirement timestamp to avoid searching too old games
        retirement_ts = anchor_state_registry.functions.retirementTimestamp().call()
        print(f"Retirement timestamp: {retirement_ts}")
        
        optimal_game = None
        
        for start in range(total_games - 1, 0, -batch_size):
            end = start
            start_idx = max(0, start - batch_size + 1)
            
            games = dispute_game_factory.functions.findLatestGames(
                game_type,
                end,
                end - start_idx + 1
            ).call()
            
            # Check each game
            for game in games:
                if len(game[4]) >= 32:
                    game_ts = game[2]
                    l2_block = int.from_bytes(game[4][:32], 'big')
                    parsed_game = {
                            'index': game[0],
                            'metadata': _ensure_hex(game[1]),
                            'timestamp': game[2],
                            'rootClaim': _ensure_hex(game[3]),
                            'extraData': _ensure_hex(game[4]),
                            'l2BlockNumber': l2_block
                        }
                    if l2_block >= l2_block_number and game_ts >= retirement_ts:
                        optimal_game = parsed_game
                    elif optimal_game:
                        # Found the boundary - now validate with AnchorStateRegistry
                        _, _, proxy = dispute_game_factory.functions.gameAtIndex(optimal_game['index']).call()
                        
                        # Check all anchor state registry flags
                        validation_errors = []
                        try:
                            is_game_proper = anchor_state_registry.functions.isGameProper(proxy).call()
                            if not is_game_proper:
                                validation_errors.append("Game is not proper (might be blacklisted or system paused)")
                                
                            is_game_respected = anchor_state_registry.functions.isGameRespected(proxy).call()
                            if not is_game_respected:
                                validation_errors.append("Game is not respected (wrong game type)")
                                
                            if validation_errors:
                                print(f"\n⚠️  Game {optimal_game['index']} validation failed:")
                                for error in validation_errors:
                                    print(f"   - {error}")
                                optimal_game = None  # Reset and continue searching
                                continue
                        except Exception as e:
                            print(f"\n⚠️  Could not validate game {optimal_game['index']}: {e}")
                            optimal_game = None
                            continue
                            
                        return {'can_prove': True, 'game': optimal_game, 'recent_games': None}
            return {'can_prove': False, 'game': None, 'recent_games': [parsed_game]}
        
    except Exception as e:
        return {'can_prove': False, 'game': None, 'recent_games': [], 'error': str(e)}


def get_withdrawal_hash_storage_slot(withdrawal_hash: bytes) -> bytes:
    """Calculate storage slot for withdrawal hash in L2ToL1MessagePasser."""
    # sentMessages mapping at slot 0: keccak256(withdrawalHash . uint256(0))
    return keccak(encode(['bytes32', 'uint256'], [withdrawal_hash, 0]))


def get_withdrawal_proof(w3_l2: Web3, withdrawal_hash: bytes, l2_block_number: int) -> List[str]:
    """Get Merkle Patricia proof for withdrawal from L2."""
    storage_slot = get_withdrawal_hash_storage_slot(withdrawal_hash)
    
    proof_response = w3_l2.manager.request_blocking(
        "eth_getProof",
        [L2_MESSAGE_PASSER, [f"0x{storage_slot.hex()}"], hex(l2_block_number)]
    )
    
    storage_proof = proof_response['storageProof'][0]['proof']
    return _maybe_add_proof_node(storage_slot.hex(), storage_proof)


def build_output_root_proof(w3_l2: Web3, l2_block_number: int, storage_hash: str) -> Dict[str, str]:
    """Build output root proof from L2 block data."""
    l2_block = w3_l2.eth.get_block(l2_block_number)
    
    return {
        'version': ZERO_VERSION,
        'stateRoot': _ensure_hex(l2_block['stateRoot']),
        'messagePasserStorageRoot': _ensure_hex(storage_hash),
        'latestBlockhash': _ensure_hex(l2_block['hash'])
    }


def build_withdrawal_transaction(event_args: Dict) -> Tuple:
    """Build withdrawal transaction tuple from MessagePassed event."""
    return (
        event_args['nonce'],
        event_args['sender'],
        event_args['target'],
        event_args['value'],
        event_args['gasLimit'],
        event_args['data']
    )


def build_prove_transaction(
    portal: Any,
    withdrawal_tx: Tuple,
    l2_output_index: int,
    output_root_proof: Dict[str, str],
    withdrawal_proof: List[str],
    sender: str
    ) -> Dict:
    """Build proveWithdrawalTransaction for OptimismPortal."""
    # Format proofs for contract call
    formatted_output_proof = (
        output_root_proof['version'],
        output_root_proof['stateRoot'],
        output_root_proof['messagePasserStorageRoot'],
        output_root_proof['latestBlockhash']
    )
    
    # Convert withdrawal proof to bytes
    withdrawal_proof_bytes = [
        bytes.fromhex(p[2:] if p.startswith('0x') else p) for p in withdrawal_proof
    ]
    
    tx_params = {
        'from': sender,
        'gas': 500000,
    }
    
    return portal.functions.proveWithdrawalTransaction(
        withdrawal_tx,
        l2_output_index,
        formatted_output_proof,
        withdrawal_proof_bytes
    ).build_transaction(tx_params)


def estimate_prove_gas(
    portal: Any,
    withdrawal_tx: Tuple,
    l2_output_index: int,
    output_root_proof: Dict[str, str],
    withdrawal_proof: List[str],
    sender: str
) -> int:
    """Estimate gas for proveWithdrawalTransaction with error handling."""
    # Format proofs for contract call
    formatted_output_proof = (
        output_root_proof['version'],
        output_root_proof['stateRoot'],
        output_root_proof['messagePasserStorageRoot'],
        output_root_proof['latestBlockhash']
    )
    
    # Convert withdrawal proof to bytes
    withdrawal_proof_bytes = [
        bytes.fromhex(p[2:] if p.startswith('0x') else p) for p in withdrawal_proof
    ]
    
    try:
        return portal.functions.proveWithdrawalTransaction(
            withdrawal_tx,
            l2_output_index,
            formatted_output_proof,
            withdrawal_proof_bytes
        ).estimate_gas({'from': sender})
    except ContractCustomError as e:
        # Build error mapping from ABI
        error_map = {
            Web3.keccak(text=f"{err['name']}()")[:4].hex(): err['name']
            for err in portal.abi if err.get('type') == 'error'
        }
        
        error_selector = str(e.args[0]).replace("0x", "")
        error_name = error_map.get(error_selector, f"Unknown({error_selector})")
        
        raise ValueError(f"Gas estimation failed with error: {error_name}") from e




# Private helper functions
def _ensure_hex(value: Any) -> str:
    """Ensure value is a hex string with 0x prefix."""
    if isinstance(value, bytes):
        return '0x' + value.hex()
    elif isinstance(value, str) and not value.startswith('0x'):
        return '0x' + value
    return value


def _maybe_add_proof_node(storage_slot_hex: str, proof: List[str]) -> List[str]:
    """Add proof node if needed (Viem's maybeAddProofNode)."""
    if not proof:
        return proof
    
    try:
        # Decode last proof node
        last_node_hex = proof[-1][2:] if proof[-1].startswith('0x') else proof[-1]
        last_node = rlp.decode(bytes.fromhex(last_node_hex))
        
        # Only process branch nodes (17 elements)
        if len(last_node) != 17:
            return proof
        
        # Check if any branch matches our path
        for i in range(16):
            if last_node[i] and storage_slot_hex.endswith(hex(i)[2:]):
                return proof + [f"0x{rlp.encode(last_node[i]).hex()}"]
        
        return proof
    except Exception:
        return proof