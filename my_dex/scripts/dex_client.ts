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
  // === Provider and Program setup ===
  const provider = anchor.AnchorProvider.env();
  anchor.setProvider(provider);
  const wallet = provider.wallet as anchor.Wallet;
  const program = anchor.workspace.MyDex as anchor.Program<MyDex>;
  const connection = provider.connection;
  const payer = (provider as any).wallet.payer as Keypair;

  console.log("🔗 Wallet:", wallet.publicKey.toBase58());

  // === Create test token mints (tokenA and tokenB) ===
  console.log("🪙 Creating token mints...");
  const decimals = 6;
  const tokenAMint = await createMint(connection, payer, wallet.publicKey, null, decimals);
  const tokenBMint = await createMint(connection, payer, wallet.publicKey, null, decimals);

  // === Get/create user's ATAs for both mints ===
  const userTokenA = await getOrCreateAssociatedTokenAccount(connection, payer, tokenAMint, wallet.publicKey);
  const userTokenB = await getOrCreateAssociatedTokenAccount(connection, payer, tokenBMint, wallet.publicKey);

  // Mint some tokens to the user for testing
  await mintTo(connection, payer, tokenAMint, userTokenA.address, payer, 1_000_000_000); // 1000 tokens (6 decimals)
  await mintTo(connection, payer, tokenBMint, userTokenB.address, payer, 1_000_000_000); // 1000 tokenB (WSOL-like)

  console.log("✅ Tokens minted to user wallets");
  console.log("   tokenAMint:", tokenAMint.toBase58());
  console.log("   tokenBMint:", tokenBMint.toBase58());

  // === Derive Pool PDA ===
  const [poolPda] = anchor.web3.PublicKey.findProgramAddressSync(
    [Buffer.from("pool")],
    program.programId
  );

  // === Generate new Keypairs for vaults (Anchor will create them) ===
  const poolTokenAVault = Keypair.generate();
  const poolTokenBVault = Keypair.generate();

  console.log("🏦 Pool PDA:", poolPda.toBase58());
  console.log("   poolTokenAVault:", poolTokenAVault.publicKey.toBase58());
  console.log("   poolTokenBVault:", poolTokenBVault.publicKey.toBase58());

  // === Initialize pool with initial liquidity ===
  console.log("🚀 Initializing pool...");
  const initial = 500_000_000; // 500 tokens (6 decimals)

  await program.methods
    .initialize(new anchor.BN(initial), new anchor.BN(initial))
    .accounts({
      user: wallet.publicKey,
      pool: poolPda,
      tokenAVault: poolTokenAVault.publicKey,
      tokenBVault: poolTokenBVault.publicKey,
      userTokenA: userTokenA.address,
      userTokenB: userTokenB.address,
      tokenAMint: tokenAMint,
      tokenBMint: tokenBMint,
      systemProgram: anchor.web3.SystemProgram.programId,
      tokenProgram: TOKEN_PROGRAM_ID,
      rent: anchor.web3.SYSVAR_RENT_PUBKEY,
    } as any)
    .signers([poolTokenAVault, poolTokenBVault])
    .rpc();

  console.log("✅ Pool initialized!");

  // === BUY: swap WSOL(tokenB) -> tokenA ===
  const amountIn = new anchor.BN(100_000_000); // 100 tokenB
  console.log("💱 Swapping WSOL → TokenA ...");

  await program.methods
    .buy(amountIn)
    .accounts({
      user: wallet.publicKey,
      pool: poolPda,
      userTokenA: userTokenA.address,
      userTokenB: userTokenB.address,
      poolTokenAVault: poolTokenAVault.publicKey,
      poolTokenBVault: poolTokenBVault.publicKey,
      tokenAMint: tokenAMint,
      tokenBMint: tokenBMint,
      tokenProgram: TOKEN_PROGRAM_ID,
    } as any)
    .rpc();

  console.log("✅ Buy transaction complete");

  // === SELL: swap TokenA -> WSOL(tokenB) ===
  const amountSell = new anchor.BN(50_000_000); // 50 tokenA
  console.log("💱 Swapping TokenA → WSOL ...");

  await program.methods
    .sell(amountSell)
    .accounts({
      user: wallet.publicKey,
      pool: poolPda,
      userTokenA: userTokenA.address,
      userTokenB: userTokenB.address,
      poolTokenAVault: poolTokenAVault.publicKey,
      poolTokenBVault: poolTokenBVault.publicKey,
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

