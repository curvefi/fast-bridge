# Arbitrum Withdrawal V3

Clean, self-contained script for checking status and executing Arbitrum withdrawals.

## Features

- Automatically finds the correct proof size for withdrawals
- Works with current Arbitrum Nitro implementation (uses SendRootUpdated events)
- Auto-detects proxy contracts and fetches implementation ABIs
- Checks withdrawal status (pending, ready, executed)
- Supports dry-run mode for safety

## Usage

1. Set environment variables:
   ```bash
   export DRPC_API_KEY=your_drpc_key
   export WEB3_TESTNET_PK=your_private_key  # Only needed for execution
   ```

2. Configure the withdrawal in `arb_withdrawal.py`:
   ```python
   TX_HASH = "your_withdrawal_tx_hash"
   DRY_RUN = True  # Set to False to execute
   ```

3. Run the script:
   ```bash
   uv run python arb_withdrawal.py
   ```

## Files

- `arb_withdrawal.py` - Main withdrawal script
- `fetch_abis.py` - Fetches required contract ABIs from Etherscan (auto-detects proxies)
- `abis/` - Contract ABI files
  - `Rollup_impl.json` - Rollup implementation ABI (auto-fetched from proxy)
  - `Outbox_impl.json` - Outbox implementation ABI (auto-fetched from proxy)
  - `ArbSys.json` - Arbitrum system contract ABI
  - `NodeInterface.json` - Node interface ABI

## Technical Notes

The script handles the fact that `OutboxEntryCreated` events don't exist in the current Arbitrum implementation. Instead, it:
1. Tries different proof sizes to find a valid merkle root
2. Verifies the root exists in the Outbox contract's `roots` mapping
3. Optionally finds the corresponding `SendRootUpdated` event for timestamp verification

The `fetch_abis.py` script automatically detects when a contract is a proxy and fetches the implementation ABI instead, ensuring compatibility with upgradeable contracts.
EOF < /dev/null