#!/usr/bin/env python3
"""
Close a (possibly non-ATA) SPL token account and send remaining lamports to recipient.
Works for WSOL (will convert wrapped SOL back to native SOL when closing).

Usage example:
  python3 close_token_account.py \
    --account Ek5qA7RtBjQmQx7cZQpYDLWHHoPjwzaTjk181NfZwZGS \
    --keypair ~/.config/solana/id.json \
    --recipient 86pmdaDr55XJHXdQvCX1KWQoAVDc49HT6K8mrJWs8EBa \
    --url https://api.devnet.solana.com
"""

import argparse
import asyncio
import json
import os
import sys

from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction
from solders.message import MessageV0
from spl.token.instructions import close_account, CloseAccountParams
from spl.token.constants import TOKEN_PROGRAM_ID

def load_keypair(path: str) -> Keypair:
    path = os.path.expanduser(path)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Keypair not found: {path}")
    data = json.load(open(path, "r"))
    if isinstance(data, list):
        b = bytes(data)
        if len(b) == 64:
            return Keypair.from_bytes(b)
        if len(b) == 32:
            return Keypair.from_seed(b)
        raise ValueError(f"Unexpected key file length: {len(b)} (expected 32 or 64 ints)")
    # if someone passed base58 or other format, try bytes decode
    raise ValueError("Unsupported keypair file format. Expected JSON array of ints (solana CLI format).")

async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--account", required=True, help="Token account pubkey to close (e.g. Ek5q...)")
    p.add_argument("--recipient", required=False, help="Where to send recovered SOL (defaults to keypair pubkey)")
    p.add_argument("--keypair", required=False, default="~/.config/solana/id.json", help="Path to signer keypair (default ~/.config/solana/id.json)")
    p.add_argument("--url", required=False, default="https://api.devnet.solana.com", help="RPC URL (default devnet)")
    p.add_argument("--no-confirm", action="store_true", help="Do not ask for interactive confirmation")
    args = p.parse_args()

    try:
        owner_kp = load_keypair(args.keypair)
    except Exception as e:
        print("Failed to load keypair:", e)
        sys.exit(1)

    payer_pubkey = owner_kp.pubkey()
    token_account = Pubkey.from_string(args.account)
    recipient = Pubkey.from_string(args.recipient) if args.recipient else payer_pubkey

    print(f"RPC: {args.url}")
    print(f"Token account to close: {token_account}")
    print(f"Payer/owner: {payer_pubkey}")
    print(f"Recipient (where recovered SOL will go): {recipient}")

    if not args.no_confirm:
        ans = input("Proceed to close the token account? (y/N) > ").strip().lower()
        if ans != "y":
            print("Aborted by user.")
            return

    rpc = AsyncClient(args.url)
    async with rpc:
        # 1) Basic checks
        info = await rpc.get_account_info_json_parsed(token_account)
        if info.value is None:
            print("Account not found on chain.")
            return

        acct_owner = info.value.owner
        print(f" - account.owner = {acct_owner}")
        if str(acct_owner) != str(TOKEN_PROGRAM_ID):
            print("WARNING: account owner is not SPL Token program. Aborting.")
            return

        # show balances for debugging
        bal_before_owner = await rpc.get_balance(payer_pubkey)
        bal_before_token = await rpc.get_balance(token_account)
        print(f"Balance before: owner={bal_before_owner.value/1e9:.9f} SOL, token_account lamports={bal_before_token.value/1e9:.9f} SOL")

        # 2) Build close instruction
        close_ix = close_account(
            CloseAccountParams(
                program_id=TOKEN_PROGRAM_ID,
                account=token_account,
                dest=recipient,
                owner=payer_pubkey,
            )
        )

        # 3) Build and sign versioned transaction
        latest = await rpc.get_latest_blockhash()
        recent_blockhash = latest.value.blockhash

        message = MessageV0.try_compile(
            payer=payer_pubkey,
            instructions=[close_ix],
            address_lookup_table_accounts=[],
            recent_blockhash=recent_blockhash,
        )

        # signers: include payer; if owner != payer you'd include owner Keypair too (here they are same)
        signers = [owner_kp]

        tx = VersionedTransaction(message, signers)

        print("Sending close transaction...")
        resp = await rpc.send_transaction(tx)
        # resp may be object with value field or raise error
        print("RPC send response:", resp)

        # optionally confirm / wait a moment
        print("Waiting for confirmation...")
        await rpc.confirm_transaction(resp.value)

        bal_after_owner = await rpc.get_balance(payer_pubkey)
        bal_after_token = await rpc.get_balance(token_account)
        print(f"Balance after: owner={bal_after_owner.value/1e9:.9f} SOL, token_account lamports={bal_after_token.value/1e9:.9f} SOL")
        print("Done. If transaction succeeded, token account should be closed and lamports returned to recipient.")

if __name__ == "__main__":
    asyncio.run(main())
