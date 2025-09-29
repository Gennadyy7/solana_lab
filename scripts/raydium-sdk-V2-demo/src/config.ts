import { Raydium, TxVersion, parseTokenAccountResp } from '@raydium-io/raydium-sdk-v2'
import { Connection, Keypair, clusterApiUrl } from '@solana/web3.js'
import { TOKEN_PROGRAM_ID, TOKEN_2022_PROGRAM_ID } from '@solana/spl-token'
import bs58 from 'bs58'

// 🔑 Твой кошелёк на Devnet (секретный ключ в виде массива чисел)
const SECRET_KEY = new Uint8Array([
  180, 48, 117, 25, 198, 95, 217, 140, 155, 93, 139, 41, 240, 229, 0, 50,
  212, 144, 193, 16, 130, 60, 156, 42, 36, 162, 56, 148, 10, 10, 108, 113,
  105, 127, 185, 197, 83, 147, 221, 128, 143, 230, 22, 39, 150, 132, 23, 175,
  3, 160, 73, 218, 104, 254, 25, 205, 243, 147, 133, 141, 139, 40, 3, 81
])
export const owner: Keypair = Keypair.fromSecretKey(SECRET_KEY)

// 🌐 RPC для Devnet
export const connection = new Connection('https://api.devnet.solana.com')
// export const connection = new Connection('https://devnet.helius-rpc.com/?api-key=b84312a3-890d-4d13-9c88-c5645a865c21')


// Версия транзакции
export const txVersion = TxVersion.V0

// ⚠️ Работаем на devnet
const cluster = 'devnet'

let raydium: Raydium | undefined
export const initSdk = async (params?: { loadToken?: boolean }) => {
  if (raydium) return raydium

  console.log(`connect to rpc ${connection.rpcEndpoint} in ${cluster}`)
  raydium = await Raydium.load({
    owner,
    connection,
    cluster,
    disableFeatureCheck: true,
    disableLoadToken: !params?.loadToken,
    blockhashCommitment: 'finalized',
    urlConfigs: {
      BASE_HOST: 'https://api-v3-devnet.raydium.io',
      OWNER_BASE_HOST: 'https://owner-v1-devnet.raydium.io',
      SWAP_HOST: 'https://transaction-v1-devnet.raydium.io',
      CPMM_LOCK: 'https://dynamic-ipfs-devnet.raydium.io/lock/cpmm/position',
    },
  })

  return raydium
}

// Функция для загрузки балансов — не трогаем
export const fetchTokenAccountData = async () => {
  const solAccountResp = await connection.getAccountInfo(owner.publicKey)
  const tokenAccountResp = await connection.getTokenAccountsByOwner(owner.publicKey, { programId: TOKEN_PROGRAM_ID })
  const token2022Req = await connection.getTokenAccountsByOwner(owner.publicKey, { programId: TOKEN_2022_PROGRAM_ID })
  const tokenAccountData = parseTokenAccountResp({
    owner: owner.publicKey,
    solAccountResp,
    tokenAccountResp: {
      context: tokenAccountResp.context,
      value: [...tokenAccountResp.value, ...token2022Req.value],
    },
  })
  return tokenAccountData
}

// Необязательные поля — можно оставить или удалить
export const grpcUrl = '<YOUR_GRPC_URL>'
export const grpcToken = '<YOUR_GRPC_TOKEN>'
