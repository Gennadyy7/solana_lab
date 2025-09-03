import argparse

from common import (
    estimate_simple_transfer_fee,
    get_client,
    lamports_from_sol,
    load_keypair,
    parse_pubkey,
    print_balances,
    send_transfer_transaction,
    wait_for_confirmation,
)
from solana.constants import LAMPORTS_PER_SOL


def main():
    parser = argparse.ArgumentParser(description="Transfer lamports between addresses")
    parser.add_argument("--from-keypair", required=True, help="Path to sender's keypair file")
    parser.add_argument("--to", required=True, help="Recipient's public key")
    amt = parser.add_mutually_exclusive_group()
    amt.add_argument("--sol", help="Amount in SOL (decimal)", default="1")
    amt.add_argument("--lamports", type=int, help="Amount in lamports (integer)")
    parser.add_argument("--rpc", help="RPC URL")
    args = parser.parse_args()

    client = get_client(args.rpc)
    from_keypair = load_keypair(args.from_keypair)
    to_pub = parse_pubkey(args.to)
    lamports = args.lamports if args.lamports is not None else lamports_from_sol(args.sol)

    if lamports <= 0:
        print("Сумма перевода должна быть больше 0.")
        return

    balance_resp = client.get_balance(from_keypair.pubkey())
    balance = balance_resp.value if balance_resp.value is not None else 0
    print(
        f"Текущий баланс отправителя ({from_keypair.pubkey()}): {balance} лампортов ({balance / LAMPORTS_PER_SOL} SOL)"
    )

    fee = estimate_simple_transfer_fee(client, from_keypair.pubkey(), to_pub)
    if balance < lamports + fee:
        print(f"Недостаточно средств: баланс ({balance}) меньше суммы ({lamports}) + комиссии ({fee}).")
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
