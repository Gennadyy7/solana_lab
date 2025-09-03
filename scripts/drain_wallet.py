import argparse

from common import (
    estimate_simple_transfer_fee,
    get_client,
    load_keypair,
    parse_pubkey,
    print_balances,
    send_transfer_transaction,
    wait_for_confirmation,
)
from solana.constants import LAMPORTS_PER_SOL


def main():
    parser = argparse.ArgumentParser(description="Transfer all available lamports to an address")
    parser.add_argument(
        "--from-keypair",
        help="Path to sender's keypair file (default: ~/.config/solana/id.json)"
    )
    parser.add_argument("--to", required=True, help="Recipient's public key")
    parser.add_argument("--rpc", help="RPC URL (default: from SOLANA_RPC_URL or solana-validator:8899)")
    args = parser.parse_args()

    client = get_client(args.rpc)
    from_keypair = load_keypair(args.from_keypair)
    to_pub = parse_pubkey(args.to)

    balance_resp = client.get_balance(from_keypair.pubkey())
    balance = balance_resp.value if balance_resp.value is not None else 0
    print(
        f"Текущий баланс отправителя ({from_keypair.pubkey()}): {balance} лампортов ({balance / LAMPORTS_PER_SOL} SOL)"
    )

    fee = estimate_simple_transfer_fee(client, from_keypair.pubkey(), to_pub)
    lamports = balance - fee

    if lamports <= 0:
        print(f"Недостаточно средств для перевода: баланс ({balance}) меньше комиссии ({fee}).")
        return

    print(
        f"Оцениваемая комиссия: {fee} лампортов. К переводу: {lamports} лампортов ({lamports / LAMPORTS_PER_SOL} SOL)."
    )

    sig = send_transfer_transaction(client, from_keypair, to_pub, lamports)
    if sig is None:
        return

    print(f"Signature: {sig}")
    ok = wait_for_confirmation(client, sig)
    print("Статус:", "✅ подтверждено" if ok else "⏳ не подтверждено (проверь позже)")

    print_balances(client, from_keypair.pubkey(), to_pub)


if __name__ == "__main__":
    main()
