#!/usr/bin/env python3
"""Fetch ABIs for Arbitrum contracts from Etherscan."""
import os
import json
import time
import requests

# Contract addresses on mainnet
CONTRACTS = {
    'L1GatewayRouter': '0x72Ce9c846789fdB6fC1f34aC4AD25Dd9ef7031ef',
    'L1ERC20Gateway': '0xa3A7B6F88361F48403514059F1F16C8E78d60EeC',
    'Inbox': '0x4Dbd4fc535Ac27206064B68FfCf827b0A60BAB3f',
    'RollupProxy': '0x5eF0D09d1E6204141B4d37530808eD19f60FBa35',
    'Bridge': '0x8315177aB297bA92A06054cE80a67Ed4DBd7ed3a',
    'Outbox': '0x760723CD2e632826c38Fef8CD438A4CC7E7E1A40'
}

# Get API key from environment
ETHERSCAN_API_KEY = os.getenv('ETHERSCAN_API_KEY')
if not ETHERSCAN_API_KEY:
    raise ValueError("ETHERSCAN_API_KEY not found in environment")

# Base URL for Etherscan API
BASE_URL = "https://api.etherscan.io/api"

# Output directory
script_path = os.path.dirname(os.path.abspath(__file__))
abi_path = os.path.join(script_path, 'abi')
os.makedirs(abi_path, exist_ok=True)


def fetch_abi(contract_name: str, address: str) -> dict:
    """Fetch ABI for a contract from Etherscan."""
    # First try to get the implementation ABI if it's a proxy
    params = {
        'module': 'contract',
        'action': 'getsourcecode',
        'address': address,
        'apikey': ETHERSCAN_API_KEY
    }
    
    print(f"Fetching ABI for {contract_name} ({address})...")
    
    response = requests.get(BASE_URL, params=params)
    data = response.json()
    
    if data['status'] == '1' and data['result']:
        result = data['result'][0]
        
        # Check if it's a proxy and has implementation
        if result.get('Implementation') and result.get('Implementation') != '':
            impl_address = result['Implementation']
            print(f"  Found proxy implementation at {impl_address}")
            
            # Get implementation ABI
            impl_params = {
                'module': 'contract',
                'action': 'getabi',
                'address': impl_address,
                'apikey': ETHERSCAN_API_KEY
            }
            
            impl_response = requests.get(BASE_URL, params=impl_params)
            impl_data = impl_response.json()
            
            if impl_data['status'] == '1':
                print(f"  Using implementation ABI")
                return json.loads(impl_data['result'])
    
    # Fallback to regular ABI fetch
    params = {
        'module': 'contract',
        'action': 'getabi',
        'address': address,
        'apikey': ETHERSCAN_API_KEY
    }
    
    response = requests.get(BASE_URL, params=params)
    data = response.json()
    
    if data['status'] != '1':
        raise ValueError(f"Failed to fetch ABI for {contract_name}: {data.get('message', 'Unknown error')}")
    
    abi = json.loads(data['result'])
    return abi


def save_abi(contract_name: str, abi: dict):
    """Save ABI to JSON file."""
    output_file = os.path.join(abi_path, f"{contract_name}.json")
    with open(output_file, 'w') as f:
        json.dump(abi, f, indent=2)
    print(f"  ✅ Saved to {output_file}")


def main():
    """Fetch and save all ABIs."""
    print("Fetching Arbitrum contract ABIs from Etherscan...\n")
    
    for contract_name, address in CONTRACTS.items():
        try:
            abi = fetch_abi(contract_name, address)
            save_abi(contract_name, abi)
            # Rate limit to avoid hitting API limits
            time.sleep(0.25)
        except Exception as e:
            print(f"  ❌ Error fetching {contract_name}: {e}")
    
    print("\nDone!")


if __name__ == "__main__":
    main()