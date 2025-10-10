import * as anchor from "@coral-xyz/anchor";
import { MyDex } from "../target/types/my_dex";
import {
  TOKEN_PROGRAM_ID,
  createMint,
  getOrCreateAssociatedTokenAccount,
  mintTo,
} from "@solana/spl-token";
import { Keypair } from "@solana/web3.js";

async function main() {
  // Provider
  const provider = anchor.AnchorProvider.env();
  anchor.setProvider(provider);
  const wallet = provider.wallet as anchor.Wallet;
  const program = anchor.workspace.MyDex as anchor.Program<MyDex>;
  const connection = provider.connection;
  const payer = (provider as any).wallet.payer as Keypair; // for spl-token helpers

  console.log("🔗 Wallet:", wallet.publicKey.toBase58());

  // === Create two test mints (tokenA and tokenB) ===
  console.log("🪙 Creating token mints...");
  const decimals = 6;
  const tokenAMint = await createMint(connection, payer, wallet.publicKey, null, decimals);
  const tokenBMint = await createMint(connection, payer, wallet.publicKey, null, decimals);

  // === Get/create user's ATA for both mints ===
  const userTokenA = await getOrCreateAssociatedTokenAccount(connection, payer, tokenAMint, wallet.publicKey);
  const userTokenB = await getOrCreateAssociatedTokenAccount(connection, payer, tokenBMint, wallet.publicKey);

  // Mint some tokens to the user for testing
  await mintTo(connection, payer, tokenAMint, userTokenA.address, payer, 1_000_000_000); // 1000 tokens (with 6 decimals)
  await mintTo(connection, payer, tokenBMint, userTokenB.address, payer, 1_000_000_000); // 1000 tokenB (WSOL-like)

  console.log("✅ Tokens minted to user wallets");
  console.log("   tokenAMint:", tokenAMint.toBase58());
  console.log("   tokenBMint:", tokenBMint.toBase58());

  // === Pool PDA and pool vaults (ATAs owned by PDA) ===
  const [poolPda] = anchor.web3.PublicKey.findProgramAddressSync(
    [Buffer.from("pool")],
    program.programId
  );

  // create/get associated token accounts for the PDA (owner = poolPda)
  const poolTokenAVault = await getOrCreateAssociatedTokenAccount(connection, payer, tokenAMint, poolPda, true);
  const poolTokenBVault = await getOrCreateAssociatedTokenAccount(connection, payer, tokenBMint, poolPda, true);

  console.log("🏦 Pool PDA:", poolPda.toBase58());
  console.log("   poolTokenAVault:", poolTokenAVault.address.toBase58());
  console.log("   poolTokenBVault:", poolTokenBVault.address.toBase58());

  // === Initialize pool with initial liquidity ===
  console.log("🚀 Initializing pool...");
  // initial amounts (with decimals): e.g. 500 = 500 * 10^decimals
  const initial = 500_000_000; // 500 tokens (6 decimals)
  await program.methods
    .initialize(new anchor.BN(initial), new anchor.BN(initial))
    .accounts({
      user: wallet.publicKey,
      pool: poolPda,
      tokenAVault: poolTokenAVault.address,
      tokenBVault: poolTokenBVault.address,
      userTokenA: userTokenA.address,
      userTokenB: userTokenB.address,
      tokenAMint: tokenAMint,
      tokenBMint: tokenBMint,
      systemProgram: anchor.web3.SystemProgram.programId,
      tokenProgram: TOKEN_PROGRAM_ID,
      rent: anchor.web3.SYSVAR_RENT_PUBKEY,
    } as any) // <-- cast to any to avoid strict TS account shape errors
    .rpc();

  console.log("✅ Pool initialized!");

  // === BUY: swap WSOL(tokenB) -> tokenA ===
  const amountIn = new anchor.BN(100_000_000); // means 100 tokenB (6 decimals)
  console.log("💱 Swapping WSOL → TokenA ...");
  await program.methods
    .buy(amountIn)
    .accounts({
      user: wallet.publicKey,
      pool: poolPda,
      userTokenA: userTokenA.address,
      userTokenB: userTokenB.address,
      poolTokenAVault: poolTokenAVault.address,
      poolTokenBVault: poolTokenBVault.address,
      tokenAMint: tokenAMint,
      tokenBMint: tokenBMint,
      tokenProgram: TOKEN_PROGRAM_ID,
    } as any)
    .rpc();

  console.log("✅ Buy transaction complete");

  // === SELL: tokenA -> WSOL(tokenB) ===
  const amountSell = new anchor.BN(50_000_000); // 50 tokenA
  console.log("💱 Swapping TokenA → WSOL ...");
  await program.methods
    .sell(amountSell)
    .accounts({
      user: wallet.publicKey,
      pool: poolPda,
      userTokenA: userTokenA.address,
      userTokenB: userTokenB.address,
      poolTokenAVault: poolTokenAVault.address,
      poolTokenBVault: poolTokenBVault.address,
      tokenAMint: tokenAMint,
      tokenBMint: tokenBMint,
      tokenProgram: TOKEN_PROGRAM_ID,
    } as any)
    .rpc();

  console.log("✅ Sell transaction complete");

  // === Final balances ===
  const refreshedA = await connection.getTokenAccountBalance(userTokenA.address);
  const refreshedB = await connection.getTokenAccountBalance(userTokenB.address);

  console.log(`📊 Final balances:`);
  console.log(`   Token A: ${refreshedA.value.uiAmount}`);
  console.log(`   Token B (WSOL): ${refreshedB.value.uiAmount}`);
}

main().catch((err) => {
  console.error("❌ Error:", err);
  process.exit(1);
});

