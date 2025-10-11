import * as anchor from "@coral-xyz/anchor";
import {
  TOKEN_PROGRAM_ID,
  createMint,
  getAssociatedTokenAddressSync,
  createAssociatedTokenAccountInstruction,
  mintTo,
  createTransferInstruction,
} from "@solana/spl-token";
import {
  PublicKey,
  SystemProgram,
  Transaction,
  Keypair,
} from "@solana/web3.js";

const RATE = 2; // 1 WSOL = 2 YOUR_TOKEN
const DECIMALS = 6;

async function main() {
  const provider = anchor.AnchorProvider.env();
  anchor.setProvider(provider);
  const program = anchor.workspace.MyDex as anchor.Program;
  const wallet = provider.wallet as anchor.Wallet;
  const payer = (provider as any).wallet.payer as Keypair;
  const conn = provider.connection;

  console.log("🔗 Wallet:", wallet.publicKey.toBase58());

  // 1️⃣ Создаём тестовые mint'ы
  console.log("🪙 Creating token mints...");
  const myTokenMint = await createMint(conn, payer, wallet.publicKey, null, DECIMALS);
  const wsolMint = await createMint(conn, payer, wallet.publicKey, null, DECIMALS);
  console.log("   myTokenMint:", myTokenMint.toBase58());
  console.log("   wsolMint:   ", wsolMint.toBase58());

  // 2️⃣ PDA пула (совпадает с Rust seeds)
  const [poolPda] = PublicKey.findProgramAddressSync(
    [Buffer.from("pool"), myTokenMint.toBuffer(), wsolMint.toBuffer()],
    program.programId
  );
  console.log("🏦 poolPda:", poolPda.toBase58());

  // 3️⃣ ATA для пула (allowOwnerOffCurve = true)
  const poolTokenAAccount = getAssociatedTokenAddressSync(myTokenMint, poolPda, true);
  const poolTokenBAccount = getAssociatedTokenAddressSync(wsolMint, poolPda, true);
  console.log("   poolTokenA (vault):", poolTokenAAccount.toBase58());
  console.log("   poolTokenB (vault):", poolTokenBAccount.toBase58());

  // 4️⃣ ATA пользователя
  const userTokenA = getAssociatedTokenAddressSync(myTokenMint, wallet.publicKey);
  const userTokenB = getAssociatedTokenAddressSync(wsolMint, wallet.publicKey);
  console.log("   userTokenA:", userTokenA.toBase58());
  console.log("   userTokenB:", userTokenB.toBase58());

  // 5️⃣ Создаём недостающие ATAs
  const createAtasTx = new Transaction();
  const infos = await conn.getMultipleAccountsInfo([
    userTokenA,
    userTokenB,
    poolTokenAAccount,
    poolTokenBAccount,
  ]);

  if (!infos[0]) {
    createAtasTx.add(
      createAssociatedTokenAccountInstruction(
        wallet.publicKey,
        userTokenA,
        wallet.publicKey,
        myTokenMint
      )
    );
  }
  if (!infos[1]) {
    createAtasTx.add(
      createAssociatedTokenAccountInstruction(
        wallet.publicKey,
        userTokenB,
        wallet.publicKey,
        wsolMint
      )
    );
  }
  if (!infos[2]) {
    createAtasTx.add(
      createAssociatedTokenAccountInstruction(
        wallet.publicKey,
        poolTokenAAccount,
        poolPda,
        myTokenMint
      )
    );
  }
  if (!infos[3]) {
    createAtasTx.add(
      createAssociatedTokenAccountInstruction(
        wallet.publicKey,
        poolTokenBAccount,
        poolPda,
        wsolMint
      )
    );
  }

  if (createAtasTx.instructions.length > 0) {
    console.log("🔧 Creating missing ATAs...");
    await provider.sendAndConfirm(createAtasTx);
    console.log("   ATAs created.");
  } else {
    console.log("   All ATAs already exist.");
  }

  // 6️⃣ Минтим тестовые токены пользователю
  console.log("💸 Minting test tokens...");
  await mintTo(conn, payer, myTokenMint, userTokenA, payer, BigInt(1_000_000_000)); // 1000 токенов
  await mintTo(conn, payer, wsolMint, userTokenB, payer, BigInt(500_000_000)); // 500 WSOL
  console.log("   Minted.");

  // 7️⃣ Инициализация пула
  console.log("⚙️ Initializing pool...");
  await program.methods
    .initialize(new anchor.BN(RATE))
    .accounts({
      pool: poolPda,
      tokenAMint: myTokenMint,
      tokenBMint: wsolMint,
      tokenAVault: poolTokenAAccount,
      tokenBVault: poolTokenBAccount,
      user: wallet.publicKey,
      systemProgram: SystemProgram.programId,
      tokenProgram: TOKEN_PROGRAM_ID,
      rent: anchor.web3.SYSVAR_RENT_PUBKEY,
    })
    .rpc();
  console.log("   Pool initialized.");

  // 8️⃣ Заливаем ликвидность (user → pool)
  console.log("🏦 Adding liquidity to pool...");
  const depositTx = new Transaction();
  depositTx.add(
    createTransferInstruction(
      userTokenA,
      poolTokenAAccount,
      wallet.publicKey,
      200_000_000, // 200 токенов
      [],
      TOKEN_PROGRAM_ID
    )
  );
  depositTx.add(
    createTransferInstruction(
      userTokenB,
      poolTokenBAccount,
      wallet.publicKey,
      100_000_000, // 100 WSOL
      [],
      TOKEN_PROGRAM_ID
    )
  );
  await provider.sendAndConfirm(depositTx);
  console.log("   Liquidity added.");

  // 9️⃣ BUY: отправляем WSOL → получаем свой токен
  const amountB = 10_000_000; // 10 WSOL
  console.log(`💱 BUY: ${amountB / 10 ** DECIMALS} WSOL -> tokens`);
  await program.methods
    .buy(new anchor.BN(amountB))
    .accounts({
      pool: poolPda,
      user: wallet.publicKey,
      userAAta: userTokenA,
      userBAta: userTokenB,
      tokenAVault: poolTokenAAccount,
      tokenBVault: poolTokenBAccount,
      tokenProgram: TOKEN_PROGRAM_ID,
    })
    .rpc();
  console.log("   BUY complete.");

  // 🔟 SELL: отправляем свои токены → получаем WSOL
  const amountA = 20_000_000; // 20 токенов
  console.log(`💱 SELL: ${amountA / 10 ** DECIMALS} TOKEN -> WSOL`);
  await program.methods
    .sell(new anchor.BN(amountA))
    .accounts({
      pool: poolPda,
      user: wallet.publicKey,
      userAAta: userTokenA,
      userBAta: userTokenB,
      tokenAVault: poolTokenAAccount,
      tokenBVault: poolTokenBAccount,
      tokenProgram: TOKEN_PROGRAM_ID,
    })
    .rpc();
  console.log("   SELL complete.");

  // 🔢 Балансы пользователя
  const aBal = await conn.getTokenAccountBalance(userTokenA);
  const bBal = await conn.getTokenAccountBalance(userTokenB);
  console.log("📊 Final user balances:");
  console.log("   MyToken:", aBal.value.uiAmount);
  console.log("   WSOL:   ", bBal.value.uiAmount);
}

main().catch((err) => {
  console.error("❌ Fatal error:", err);
  process.exit(1);
});

