from __future__ import annotations

import argparse
import base64
import json
import struct
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, getcontext
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from solana.rpc.api import Client
from solders.pubkey import Pubkey

from pythclient.pythaccounts import PythPriceInfo, PythPriceStatus

# Use high precision for currency math to avoid rounding surprises.
getcontext().prec = 28

PYTH_MAGIC = 0xA1B2C3D4
ACCOUNT_HEADER_SIZE = 16

# Mapping of shorthand symbols to Pyth product identifiers.
PYTH_SYMBOL_MAP: Dict[str, str] = {
    "SOL": "Crypto.SOL/USD",
    "BTC": "Crypto.BTC/USD",
    "ETH": "Crypto.ETH/USD",
}


@dataclass
class PythPrice:
    symbol: str
    price: Decimal
    confidence: Decimal
    status: str


@dataclass
class PoolSnapshot:
    token_balance: Decimal
    token_decimals: int
    wsol_balance: Decimal
    wsol_decimals: int

    @property
    def token_price_in_wsol(self) -> Decimal:
        """Return the pool quote for one custom token in units of WSOL."""
        if self.token_balance == 0:
            raise ValueError("Token vault balance is zero; cannot derive a price.")
        # Convert both balances into UI units before taking the ratio.
        token_ui = self.token_balance
        wsol_ui = self.wsol_balance
        return wsol_ui / token_ui

def parse_header(data: bytes) -> Tuple[int, int, int]:
    if len(data) < ACCOUNT_HEADER_SIZE:
        raise ValueError("Account data too short for Pyth header")
    magic, version, account_type, size = struct.unpack_from("<IIII", data, 0)
    if magic != PYTH_MAGIC:
        raise ValueError("Account data does not match Pyth magic constant")
    if size > len(data):
        raise ValueError("Pyth account size field larger than buffer")
    return version, account_type, size


def decode_account_data(client: Client, pubkey: str) -> Tuple[bytes, int, int]:
    resp = client.get_account_info(Pubkey.from_string(pubkey))
    value = resp.value
    if value is None:
        raise ValueError(f"Account {pubkey} is unavailable")
    data_field = value.data
    if isinstance(data_field, bytes):
        raw = data_field
    else:
        data_b64, encoding = data_field
        if encoding != "base64":
            raise ValueError(f"Unexpected encoding for {pubkey}: {encoding}")
        raw = base64.b64decode(data_b64)
    version, account_type, size = parse_header(raw)
    return raw[:size], version, account_type


def parse_mapping_account(data: bytes) -> Tuple[List[str], Optional[str]]:
    offset = ACCOUNT_HEADER_SIZE
    num_products, _unused, next_key_bytes = struct.unpack_from("<II32s", data, offset)
    offset += struct.calcsize("<II32s")

    product_keys: List[str] = []
    for _ in range(num_products):
        key_bytes = data[offset:offset + 32]
        offset += 32
        if key_bytes == b"\x00" * 32:
            continue
        product_keys.append(str(Pubkey.from_bytes(key_bytes)))

    next_key = None if next_key_bytes == b"\x00" * 32 else str(Pubkey.from_bytes(next_key_bytes))
    return product_keys, next_key


def parse_product_account(data: bytes) -> Tuple[Optional[str], Dict[str, str]]:
    offset = ACCOUNT_HEADER_SIZE
    first_price_bytes = data[offset:offset + 32]
    offset += 32

    attrs: Dict[str, str] = {}
    data_len = len(data)
    while offset < data_len:
        key_len = data[offset]
        offset += 1
        if key_len == 0:
            break
        key = data[offset:offset + key_len].decode("utf-8")
        offset += key_len
        value_len = data[offset]
        offset += 1
        value = data[offset:offset + value_len].decode("utf-8")
        offset += value_len
        attrs[key] = value

    first_price = None if first_price_bytes == b"\x00" * 32 else str(Pubkey.from_bytes(first_price_bytes))
    return first_price, attrs


def parse_price_account(data: bytes, version: int) -> Tuple[Decimal, Decimal, str]:
    buffer = data
    offset = ACCOUNT_HEADER_SIZE
    if version == 2:
        _price_type, exponent, _num_components = struct.unpack_from("<IiI", buffer, offset)
        offset += 16  # includes an unused u32 field
        offset += 16  # last_slot, valid_slot
        offset += 48  # derivations
        offset += 9   # timestamp + min_publishers
        offset += 2   # message_sent + max_latency
        offset += 5   # reserved
        offset += 64  # product key + next price key
        offset += 32  # previous price snapshot
    elif version == 1:
        _price_type, exponent, _num_components, _unused, _last_slot, _valid_slot, _product_key, _next_key, _aggregator_key = struct.unpack_from(
            "<IiIIQQ32s32s32s", buffer, offset
        )
        offset += 128
    else:
        raise ValueError(f"Unsupported Pyth price account version {version}")

    price_info = PythPriceInfo.deserialise(buffer, offset, exponent=exponent)
    price = Decimal(str(price_info.price))
    confidence = Decimal(str(price_info.confidence_interval))
    status = price_info.price_status.name if isinstance(price_info.price_status, PythPriceStatus) else str(price_info.price_status)
    return price, confidence, status

PYTH_ACCOUNT_MAPPING = 1
PYTH_ACCOUNT_PRODUCT = 2
PYTH_ACCOUNT_PRICE = 3

PYTH_MAPPING_DEVNET = "BmA9Z6FjioHJPpjT39QazZyhDRUdZy2ezwx4GiDdE2u2"


def fetch_pyth_prices(client: Client, desired_symbols: Iterable[str]) -> Dict[str, PythPrice]:
    desired = set(desired_symbols)
    prices: Dict[str, PythPrice] = {}
    next_mapping = PYTH_MAPPING_DEVNET

    while next_mapping and len(prices) < len(desired):
        mapping_data, _, account_type = decode_account_data(client, next_mapping)
        if account_type != PYTH_ACCOUNT_MAPPING:
            raise ValueError(f"Account {next_mapping} is not a Pyth mapping account")
        product_keys, next_mapping = parse_mapping_account(mapping_data)

        for product_key in product_keys:
            product_data, _, product_type = decode_account_data(client, product_key)
            if product_type != PYTH_ACCOUNT_PRODUCT:
                continue
            first_price_key, attrs = parse_product_account(product_data)
            symbol = attrs.get("symbol")
            if symbol not in desired or first_price_key is None:
                continue

            price_data, price_version, price_type = decode_account_data(client, first_price_key)
            if price_type != PYTH_ACCOUNT_PRICE:
                continue
            price, confidence, status = parse_price_account(price_data, price_version)
            prices[symbol] = PythPrice(symbol=symbol, price=price, confidence=confidence, status=status)

            if len(prices) == len(desired):
                break

    missing = desired - set(prices.keys())
    if missing:
        raise RuntimeError(f"Missing Pyth symbols: {', '.join(sorted(missing))}")
    return prices


def load_swap_info(path: Path) -> dict:
    data = json.loads(path.read_text())
    required = [
        "custom_token_mint",
        "custom_token_decimals",
        "token_a_vault",
        "token_b_vault",
    ]
    for key in required:
        if key not in data:
            raise KeyError(f"swap-info.json missing required field '{key}'")
    return data


def decimal_amount(token_resp) -> tuple[Decimal, int]:
    if token_resp.value is None:
        raise ValueError("Token account does not exist or has zero balance")
    amount = Decimal(token_resp.value.amount)
    decimals = token_resp.value.decimals
    scale = Decimal(10) ** decimals
    return amount / scale, decimals


def read_pool_snapshot(client: Client, swap_info: dict) -> PoolSnapshot:
    token_vault = Pubkey.from_string(swap_info["token_a_vault"])
    wsol_vault = Pubkey.from_string(swap_info["token_b_vault"])

    token_balance_resp = client.get_token_account_balance(token_vault)
    wsol_balance_resp = client.get_token_account_balance(wsol_vault)

    token_balance_ui, token_decimals = decimal_amount(token_balance_resp)
    wsol_balance_ui, wsol_decimals = decimal_amount(wsol_balance_resp)

    return PoolSnapshot(
        token_balance=token_balance_ui,
        token_decimals=token_decimals,
        wsol_balance=wsol_balance_ui,
        wsol_decimals=wsol_decimals,
    )


def format_decimal(value: Decimal, precision: int = 6) -> str:
    quant = Decimal(10) ** -precision
    return f"{value.quantize(quant, rounding=ROUND_HALF_UP):f}"


def run(args: argparse.Namespace) -> int:
    rpc_url = args.url

    client = Client(rpc_url)
    pyth_prices = fetch_pyth_prices(client, PYTH_SYMBOL_MAP.values())
    swap_info = load_swap_info(args.info)
    pool_snapshot = read_pool_snapshot(client, swap_info)

    sol_price = pyth_prices[PYTH_SYMBOL_MAP["SOL"]].price
    token_price_in_wsol = pool_snapshot.token_price_in_wsol
    token_price_usd = token_price_in_wsol * sol_price

    btc_price = pyth_prices[PYTH_SYMBOL_MAP["BTC"]].price
    eth_price = pyth_prices[PYTH_SYMBOL_MAP["ETH"]].price

    token_in_btc = token_price_usd / btc_price
    token_in_eth = token_price_usd / eth_price

    print("Pyth oracle prices (USD):")
    for symbol, product_name in PYTH_SYMBOL_MAP.items():
        price = pyth_prices[product_name]
        print(
            f"  {symbol}: ${format_decimal(price.price, args.precision)}"
            f"  (status={price.status}, ±{format_decimal(price.confidence, args.precision)})"
        )
    print()

    print("Pool snapshot:")
    print(
        f"  Token vault: {pool_snapshot.token_balance} units"
        f" (decimals={pool_snapshot.token_decimals})"
    )
    print(
        f"  WSOL vault: {pool_snapshot.wsol_balance} SOL"
        f" (decimals={pool_snapshot.wsol_decimals})"
    )
    print(f"  Derived token price: {format_decimal(token_price_in_wsol, args.precision)} WSOL")
    print(f"  Token price in USD: ${format_decimal(token_price_usd, args.precision)}")
    print()

    print("Token value via USD conversions:")
    print(f"  In BTC: {format_decimal(token_in_btc, args.precision)} BTC")
    print(f"  In ETH: {format_decimal(token_in_eth, args.precision)} ETH")

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Report token price information using Pyth oracle data")
    root = Path(__file__).resolve().parent
    parser.add_argument("--url", default="https://api.devnet.solana.com", help="Solana RPC endpoint")
    parser.add_argument("--info", type=Path, default=root / "swap-info.json", help="Path to swap-info.json")
    parser.add_argument("--precision", type=int, default=6, help="Decimal places to display in reports")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())