import json
import os
import asyncio
from pathlib import Path
from typing import Optional

from anchorpy import Program, Provider, Context
from solders.keypair import Keypair
from solders.pubkey import Pubkey as PublicKey
from solana.rpc.async_api import AsyncClient
from solana.constants import SYSTEM_PROGRAM_ID as SYS_PROGRAM_ID
from anchorpy.provider import Wallet


DEFAULT_RPC = os.getenv("SOLANA_RPC_URL") or "http://solana-validator:8899"
PROGRAM_ID = PublicKey("F5dqGKbj7K9TZybzNKFhViMySM6vsED5f1oAy5rmKcj3")
IDL_PATH = Path(__file__).parent.parent / "counter" / "target" / "idl" / "counter.json"


class CounterClient:
    def __init__(
        self,
        rpc_url: str = DEFAULT_RPC,
        wallet: Optional[Keypair] = None,
        program_id: PublicKey = PROGRAM_ID,
        idl_path: Path = IDL_PATH,
    ):
        self.rpc_url = rpc_url
        keypath = Path(os.path.expanduser("~/.config/solana/id.json"))
        secret_key = json.loads(keypath.read_text())
        self.wallet = wallet or Keypair.from_bytes(bytes(secret_key))
        self.program_id = program_id
        self.idl_path = idl_path
        self.client = AsyncClient(self.rpc_url)
        self.wallet_wrapper = Wallet(self.wallet)
        self.provider = Provider(self.client, self.wallet_wrapper)
        with open(self.idl_path, "r") as f:
            idl = json.load(f)
        self.program = Program(idl, self.program_id, self.provider)
        self.counter_keypair: Optional[Keypair] = None

    async def initialize(self) -> None:
        self.counter_keypair = Keypair()
        await self.program.rpc["initialize"](
            ctx=Context(
                accounts={
                    "counter": self.counter_keypair.pubkey,
                    "user": self.wallet.pubkey,
                    "system_program": SYS_PROGRAM_ID,
                },
                signers=[self.counter_keypair],
            )
        )
        print("✅ Counter initialized")

    async def increment(self) -> None:
        if not self.counter_keypair:
            raise ValueError("Counter not initialized. Call `initialize()` first.")
        await self.program.rpc["increment"](
            ctx=Context(
                accounts={
                    "counter": self.counter_keypair.pubkey,
                    "user": self.wallet.pubkey,
                }
            )
        )
        print("↗️ Incremented")

    async def decrement(self) -> None:
        if not self.counter_keypair:
            raise ValueError("Counter not initialized. Call `initialize()` first.")
        await self.program.rpc["decrement"](
            ctx=Context(
                accounts={
                    "counter": self.counter_keypair.pubkey,
                    "user": self.wallet.pubkey,
                }
            )
        )
        print("↘️ Decremented")

    async def get_count(self) -> int:
        if not self.counter_keypair:
            raise ValueError("Counter not initialized.")
        account = await self.program.account["Counter"].fetch(self.counter_keypair.pubkey)
        return account.count

    async def run_demo(self) -> None:
        await self.initialize()
        for _ in range(3):
            await self.increment()
        await self.decrement()
        final_count = await self.get_count()
        print(f"🔢 Final counter value: {final_count}")

    async def close(self) -> None:
        await self.client.close()


async def main():
    client = CounterClient()
    try:
        await client.run_demo()
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
