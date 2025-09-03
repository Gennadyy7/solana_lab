import json
import os
import time
from decimal import ROUND_DOWN, Decimal
from typing import Optional, Union

from solana.constants import LAMPORTS_PER_SOL
from solana.rpc.api import Client
from solders.keypair import Keypair
from solders.message import Message
from solders.pubkey import Pubkey
from solders.signature import Signature
from solders.system_program import TransferParams, transfer
from solders.transaction import Transaction

DEFAULT_RPC = os.getenv("SOLANA_RPC_URL") or "http://solana-validator:8899"


def get_client(rpc_url: Optional[str] = None) -> Client:
    return Client(rpc_url or DEFAULT_RPC)


def parse_pubkey(addr: str) -> Pubkey:
    try:
        return Pubkey.from_string(addr)
    except Exception as e:
        raise ValueError(f"Некорректный адрес: {addr}") from e


def lamports_from_sol(sol_str: str) -> int:
    val = (Decimal(sol_str) * Decimal(LAMPORTS_PER_SOL)).to_integral_value(rounding=ROUND_DOWN)
    return int(val)


def wait_for_confirmation(client: Client, signature: Union[str, Signature], timeout_sec: float = 30.0) -> bool:
    sig_obj = Signature.from_string(signature) if isinstance(signature, str) else signature
    start = time.time()
    while time.time() - start < timeout_sec:
        try:
            resp = client.get_signature_statuses([sig_obj])
            val = resp.value[0] if resp.value else None
            if val is not None:
                status = getattr(val, "confirmation_status", None)
                err = getattr(val, "err", None)
                confirmations = getattr(val, "confirmations", None)
                if err is not None:
                    print(f"Ошибка транзакции: {err}")
                    return False
                if status in ("confirmed", "finalized") or confirmations is None:
                    return True
            time.sleep(0.5)
        except Exception as e:
            print(f"Ошибка при проверке статуса: {e}")
            time.sleep(0.5)
    print("Таймаут: транзакция не подтверждена")
    return False


def load_keypair(path: Optional[str] = None) -> Keypair:
    path = os.path.expanduser(path or "~/.config/solana/id.json")
    with open(path, "r") as f:
        data = json.load(f)
    if isinstance(data, list):
        secret = bytes(data)
    elif isinstance(data, dict) and "secretKey" in data:
        secret = bytes(data["secretKey"])
    else:
        raise ValueError("Неизвестный формат ключа, ожидаю массив байт или поле secretKey")
    if len(secret) != 64:
        raise ValueError(f"Длина секретного ключа {len(secret)} байт, ожидаю 64")
    return Keypair.from_bytes(secret)


def estimate_simple_transfer_fee(client: Client, from_pub: Pubkey, to_pub: Pubkey, retries: int = 3) -> int:
    for attempt in range(retries):
        try:
            bh_resp = client.get_latest_blockhash()
            blockhash = bh_resp.value.blockhash
            ix = transfer(TransferParams(from_pubkey=from_pub, to_pubkey=to_pub, lamports=1))
            msg = Message.new_with_blockhash([ix], payer=from_pub, blockhash=blockhash)
            fee_resp = client.get_fee_for_message(msg)
            fee = fee_resp.value
            return int(fee) if fee is not None else 5000
        except Exception as e:
            print(f"Ошибка при оценке комиссии (попытка {attempt + 1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(0.5)
    print("Не удалось оценить комиссию, используется значение по умолчанию: 5000 лампортов")
    return 5000


def send_transfer_transaction(
        client: Client, from_keypair: Keypair, to_pub: Pubkey, lamports: int
) -> Optional[Signature]:
    try:
        ix = transfer(TransferParams(from_pubkey=from_keypair.pubkey(), to_pubkey=to_pub, lamports=lamports))
        blockhash = client.get_latest_blockhash().value.blockhash
        msg = Message.new_with_blockhash([ix], payer=from_keypair.pubkey(), blockhash=blockhash)
        tx = Transaction.new_unsigned(msg)
        tx.sign([from_keypair])
        sig = client.send_transaction(tx).value
        return sig
    except Exception as e:
        print(f"Ошибка при отправке транзакции: {e}")
        return None


def print_balances(client: Client, from_pub: Pubkey, to_pub: Pubkey) -> None:
    from_balance = client.get_balance(from_pub).value or 0
    to_balance = client.get_balance(to_pub).value or 0
    print(f"Баланс отправителя ({from_pub}): {from_balance} лампортов ({from_balance / LAMPORTS_PER_SOL} SOL)")
    print(f"Баланс получателя ({to_pub}): {to_balance} лампортов ({to_balance / LAMPORTS_PER_SOL} SOL)")
