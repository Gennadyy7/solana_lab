import argparse

from common import (
    get_client,
    lamports_from_sol,
    parse_pubkey,
    wait_for_confirmation,
)


def main():
    parser = argparse.ArgumentParser(description="Airdrop SOL на адрес")
    parser.add_argument("--to", required=True, help="Адрес получателя (Pubkey)")
    amt = parser.add_mutually_exclusive_group()
    amt.add_argument("--sol", help="Сколько SOL закинуть (десятичное число). По умолчанию 1 SOL", default="1")
    amt.add_argument("--lamports", type=int, help="Сколько лампортов закинуть (целое)")
    parser.add_argument(
        "--rpc",
        help="RPC URL (по умолчанию берётся из SOLANA_RPC_URL или solana-validator:8899)"
    )
    args = parser.parse_args()

    client = get_client(args.rpc)
    to_pub = parse_pubkey(args.to)
    lamports = args.lamports if args.lamports is not None else lamports_from_sol(args.sol)

    print(f"Запрашиваю airdrop {lamports} лампортов на {to_pub} ...")
    resp = client.request_airdrop(to_pub, lamports)
    sig = resp.value

    print(f"Signature: {sig}")
    ok = wait_for_confirmation(client, sig)
    print("Статус:", "✅ подтверждено" if ok else "⏳ не дождались подтверждения (проверь позже)")

    bal = client.get_balance(to_pub).value
    print(f"Баланс адреса {to_pub}: {bal} лампортов")


if __name__ == "__main__":
    main()
