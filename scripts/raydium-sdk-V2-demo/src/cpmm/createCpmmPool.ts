import {
  DEVNET_PROGRAM_ID,
  getCpmmPdaAmmConfigId,
  printSimulate,
} from '@raydium-io/raydium-sdk-v2'
import BN from 'bn.js'
import { initSdk, txVersion } from '../config'

export const createPool = async () => {
  try {
    const raydium = await initSdk({ loadToken: true })

    // === ТВОЙ ТОКЕН (Token-2022) ===
    const mintA = {
      address: 'mntrBoi14K4bn4QqT9pHicv3EKqvxCT4y9mS7YfJkDh',
      programId: 'TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb',
      decimals: 9,
    }

    // === WSOL (SPL Token) ===
    const mintB = {
      address: 'So11111111111111111111111111111111111111112',
      programId: 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA',
      decimals: 9,
    }

    const feeConfigs = await raydium.api.getCpmmConfigs()

    if (raydium.cluster === 'devnet') {
      feeConfigs.forEach((config) => {
        config.id = getCpmmPdaAmmConfigId(
          DEVNET_PROGRAM_ID.CREATE_CPMM_POOL_PROGRAM,
          config.index
        ).publicKey.toBase58()
      })
    }

    const wsolAmount = new BN(4_500_000_000)
    const tokenAmount = new BN(19_900_000_000_000)

    const { execute, extInfo, transaction } = await raydium.cpmm.createPool({
      programId: DEVNET_PROGRAM_ID.CREATE_CPMM_POOL_PROGRAM,
      poolFeeAccount: DEVNET_PROGRAM_ID.CREATE_CPMM_POOL_FEE_ACC,
      mintA,
      mintB,
      mintAAmount: tokenAmount,
      mintBAmount: wsolAmount,
      startTime: new BN(0),
      feeConfig: feeConfigs[0],
      associatedOnly: false,
      ownerInfo: {
        useSOLBalance: true,
      },
      txVersion,
    })

    printSimulate([transaction])

    const { txId } = await execute({ sendAndConfirm: true })
    console.log('✅ Pool created!', {
      txId,
      poolId: extInfo.address.poolId.toString(),
      tokenVaultA: extInfo.address.vaultA.toString(),
      tokenVaultB: extInfo.address.vaultB.toString(),
    })
  } catch (err) {
    console.error('❌ Ошибка при создании пула:', err)
  } finally {
    process.exit()
  }
}

createPool()

