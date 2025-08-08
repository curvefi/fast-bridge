#!/usr/bin/env python3
"""
Fetch ABIs from Etherscan for Arbitrum contracts.
Automatically detects proxy contracts and fetches implementation ABIs.
"""
import os
import json
import time
import requests
from pathlib import Path

# Contract addresses - proxies will be auto-detected
CONTRACTS = {
    # L1 Ethereum Mainnet
    "Rollup": {
        "address": "0x5eF0D09d1E6204141B4d37530808eD19f60FBa35",  # Proxy
        "chain": "mainnet"
    },
    "Outbox": {
        "address": "0x0B9857ae2D4A3DBe74ffE1d7DF045bb7F96E4840",  # Proxy
        "chain": "mainnet"
    },
    # L2 Arbitrum
    "ArbSys": {
        "address": "0x0000000000000000000000000000000000000064",
        "chain": "arbitrum"
    },
    "NodeInterface": {
        "address": "0x00000000000000000000000000000000000000C8",
        "chain": "arbitrum"
    }
}

CHAIN_IDS = {
    "mainnet": 1,
    "arbitrum": 42161
}


def fetch_abi(contract_name: str, address: str, chain: str) -> dict:
    """Fetch ABI from Etherscan v2 API, auto-detecting proxy implementations."""
    api_key = os.getenv("ETHERSCAN_API_KEY")
    if not api_key:
        raise ValueError("ETHERSCAN_API_KEY not set in environment")
    
    chain_id = CHAIN_IDS[chain]
    url = "https://api.etherscan.io/v2/api"
    
    # First, get source code to check if it's a proxy
    params = {
        "chainid": chain_id,
        "module": "contract",
        "action": "getsourcecode",
        "address": address,
        "apikey": api_key
    }
    
    print(f"Fetching {contract_name} from {chain} ({address})...")
    response = requests.get(url, params=params)
    
    if response.status_code != 200:
        raise RuntimeError(f"Failed to fetch contract info: HTTP {response.status_code}")
    
    data = response.json()
    
    # Check if it's a proxy with implementation
    impl_address = None
    if data.get("status") == "1" and data.get("result"):
        result = data["result"][0] if isinstance(data["result"], list) else data["result"]
        
        # Check for implementation address (proxy pattern)
        if result.get("Implementation") and result["Implementation"] != "":
            impl_address = result["Implementation"]
            print(f"  Detected proxy -> implementation: {impl_address}")
    
    # Now fetch the ABI (either implementation or direct)
    target_address = impl_address if impl_address else address
    abi_params = {
        "chainid": chain_id,
        "module": "contract",
        "action": "getabi",
        "address": target_address,
        "apikey": api_key
    }
    
    response = requests.get(url, params=abi_params)
    data = response.json()
    
    if data.get("status") != "1":
        print(f"  Warning: Could not fetch ABI for {contract_name}")
        print(f"  Response: {data.get('result', 'No result')}")
        return None
    
    try:
        abi = json.loads(data["result"])
        print(f"  Success! Got {len(abi)} ABI entries")
        
        # If it's a proxy, rename for clarity
        if impl_address:
            print(f"  Using implementation ABI from {impl_address}")
        
        return abi
    except json.JSONDecodeError:
        print("  Error: Invalid JSON in ABI response")
        return None


def main():
    # Create abis directory
    abi_dir = Path(__file__).parent / "abis"
    abi_dir.mkdir(exist_ok=True)
    
    print("Fetching contract ABIs from Etherscan...")
    print("=" * 60)
    
    for name, info in CONTRACTS.items():
        abi = fetch_abi(name, info["address"], info["chain"])
        
        if abi:
            # Save with _impl suffix if it's a proxy contract
            if name in ["Rollup", "Outbox"]:
                output_name = f"{name}_impl"
            else:
                output_name = name
                
            output_file = abi_dir / f"{output_name}.json"
            with open(output_file, 'w') as f:
                json.dump(abi, f, indent=2)
            print(f"  Saved to {output_file}")
            
            # Show summary of events
            events = [item for item in abi if item.get("type") == "event"]
            if events:
                event_names = [e['name'] for e in events[:5]]
                print(f"  Events: {', '.join(event_names)}")
                if len(events) > 5:
                    print(f"  ... and {len(events) - 5} more")
        else:
            print(f"  Skipping {name} (no ABI available)")
        
        # Rate limit
        time.sleep(0.5)
        print()
    
    print("=" * 60)
    print("Done! ABIs saved to abis/ directory")


if __name__ == "__main__":
    main()