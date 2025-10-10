// /app/counter/scripts/counter_client.ts
import * as anchor from "@coral-xyz/anchor";
import { Counter } from "../target/types/counter";

async function main() {
  const provider = anchor.AnchorProvider.env();
  anchor.setProvider(provider);
  const wallet = provider.wallet as anchor.Wallet;
  const program = anchor.workspace.Counter as anchor.Program<Counter>;
  const counter = anchor.web3.Keypair.generate();

  console.log("✅ Initializing counter...");
  await program.methods
    .initialize()
    .accounts({
      counter: counter.publicKey,
      user: wallet.publicKey,
    })
    .signers([counter])
    .rpc();

  console.log("↗️ Incrementing 3 times...");
  for (let i = 0; i < 3; i++) {
    await program.methods
      .increment()
      .accounts({
        counter: counter.publicKey,
        // user НЕ нужен!
      })
      .rpc();
    console.log(`  → Step ${i + 1}`);
  }

  console.log("↘️ Decrementing once...");
  await program.methods
    .decrement()
    .accounts({
      counter: counter.publicKey,
      // user НЕ нужен!
    })
    .rpc();

  const counterAccount = await program.account.counter.fetch(counter.publicKey);
  console.log(`🔢 Final counter value: ${counterAccount.count.toString()}`);
}

main().catch((err) => {
  console.error("❌ Error:", err);
  process.exit(1);
});
