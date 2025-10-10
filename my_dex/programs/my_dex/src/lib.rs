use anchor_lang::prelude::*;
use anchor_spl::token::{self, Token, TokenAccount, Transfer};

declare_id!("mntrBoi14K4bn4QqT9pHicv3EKqvxCT4y9mS7YfJkDh");

// Курс: 1 WSOL = 2 твоих токена
const WSOL_TO_TOKEN_RATE: u64 = 2;

#[program]
pub mod my_dex {
    use super::*;

    /// Initialize pool and provide initial liquidity.
    /// `initial_a` — amount of YOUR_TOKEN to deposit into pool vault A
    /// `initial_b` — amount of WSOL to deposit into pool vault B
    pub fn initialize(ctx: Context<Initialize>, initial_a: u64, initial_b: u64) -> Result<()> {
        let pool = &mut ctx.accounts.pool;
        pool.token_a_vault = ctx.accounts.token_a_vault.key();
        pool.token_b_vault = ctx.accounts.token_b_vault.key();

        // Transfer initial_a from user_token_a -> token_a_vault (user signs)
        token::transfer(
            CpiContext::new(
                ctx.accounts.token_program.to_account_info(),
                Transfer {
                    from: ctx.accounts.user_token_a.to_account_info(),
                    to: ctx.accounts.token_a_vault.to_account_info(),
                    authority: ctx.accounts.user.to_account_info(),
                },
            ),
            initial_a,
        )?;

        // Transfer initial_b from user_token_b -> token_b_vault (user signs)
        token::transfer(
            CpiContext::new(
                ctx.accounts.token_program.to_account_info(),
                Transfer {
                    from: ctx.accounts.user_token_b.to_account_info(),
                    to: ctx.accounts.token_b_vault.to_account_info(),
                    authority: ctx.accounts.user.to_account_info(),
                },
            ),
            initial_b,
        )?;

        Ok(())
    }

    /// Пользователь присылает WSOL (amount_in) и получает amount_out = amount_in * RATE ваших токенов
    pub fn buy(ctx: Context<Swap>, amount_in: u64) -> Result<()> {
        let amount_out = amount_in
            .checked_mul(WSOL_TO_TOKEN_RATE)
            .ok_or(ErrorCode::CalculationOverflow)?;

        // 1) пользователь отправляет WSOL в pool vault (user signs)
        token::transfer(
            CpiContext::new(
                ctx.accounts.token_program.to_account_info(),
                Transfer {
                    from: ctx.accounts.user_token_b.to_account_info(),
                    to: ctx.accounts.pool_token_b_vault.to_account_info(),
                    authority: ctx.accounts.user.to_account_info(),
                },
            ),
            amount_in,
        )?;

        // 2) pool (PDA) отправляет ваши токены пользователю — подписываем CPI с PDA seeds
        let (_pda, bump) = Pubkey::find_program_address(&[b"pool"], &crate::ID);
        let signer_seeds: &[&[u8]] = &[b"pool", &[bump]];

        token::transfer(
            CpiContext::new_with_signer(
                ctx.accounts.token_program.to_account_info(),
                Transfer {
                    from: ctx.accounts.pool_token_a_vault.to_account_info(),
                    to: ctx.accounts.user_token_a.to_account_info(),
                    authority: ctx.accounts.pool.to_account_info(),
                },
                &[signer_seeds],
            ),
            amount_out,
        )?;

        Ok(())
    }

    /// Пользователь отправляет ваши токены (amount_in), получает WSOL = amount_in / RATE
    pub fn sell(ctx: Context<Swap>, amount_in: u64) -> Result<()> {
        if WSOL_TO_TOKEN_RATE == 0 {
            return Err(ErrorCode::CalculationOverflow.into());
        }
        let amount_out = amount_in
            .checked_div(WSOL_TO_TOKEN_RATE)
            .ok_or(ErrorCode::InvalidAmount)?;

        // 1) пользователь отправляет ваши токены в пул (user signs)
        token::transfer(
            CpiContext::new(
                ctx.accounts.token_program.to_account_info(),
                Transfer {
                    from: ctx.accounts.user_token_a.to_account_info(),
                    to: ctx.accounts.pool_token_a_vault.to_account_info(),
                    authority: ctx.accounts.user.to_account_info(),
                },
            ),
            amount_in,
        )?;

        // 2) пул (PDA) отправляет WSOL пользователю
        let (_pda, bump) = Pubkey::find_program_address(&[b"pool"], &crate::ID);
        let signer_seeds: &[&[u8]] = &[b"pool", &[bump]];

        token::transfer(
            CpiContext::new_with_signer(
                ctx.accounts.token_program.to_account_info(),
                Transfer {
                    from: ctx.accounts.pool_token_b_vault.to_account_info(),
                    to: ctx.accounts.user_token_b.to_account_info(),
                    authority: ctx.accounts.pool.to_account_info(),
                },
                &[signer_seeds],
            ),
            amount_out,
        )?;

        Ok(())
    }
}

#[derive(Accounts)]
pub struct Initialize<'info> {
    /// payer and signer who provides initial liquidity
    #[account(mut)]
    pub user: Signer<'info>,

    /// Pool PDA account that stores vault pubkeys
    #[account(
        init,
        payer = user,
        space = 8 + 32 + 32,
        seeds = [b"pool"],
        bump
    )]
    pub pool: Account<'info, Pool>,

    /// Pool's vault for YOUR_TOKEN (created and owned by pool PDA)
    #[account(
        init,
        payer = user,
        token::mint = token_a_mint,
        token::authority = pool,
    )]
    pub token_a_vault: Account<'info, TokenAccount>,

    /// Pool's vault for WSOL (created and owned by pool PDA)
    #[account(
        init,
        payer = user,
        token::mint = token_b_mint,
        token::authority = pool,
    )]
    pub token_b_vault: Account<'info, TokenAccount>,

    /// User's ATA for YOUR_TOKEN (must have tokens to fund pool)
    #[account(mut, constraint = user_token_a.mint == token_a_mint.key())]
    pub user_token_a: Account<'info, TokenAccount>,

    /// User's ATA for WSOL (must have WSOL to fund pool)
    #[account(mut, constraint = user_token_b.mint == token_b_mint.key())]
    pub user_token_b: Account<'info, TokenAccount>,

    /// Your token mint
    /// CHECK: This is the mint account for the custom token. We don't need to deserialize it here;
    /// the program only reads its pubkey for mint checks on TokenAccount constraints.
    pub token_a_mint: UncheckedAccount<'info>,

    /// WSOL mint
    /// CHECK: This is the WSOL mint account pubkey; no deserialization required in the program.
    pub token_b_mint: UncheckedAccount<'info>,

    pub system_program: Program<'info, System>,
    pub token_program: Program<'info, Token>,
    pub rent: Sysvar<'info, Rent>,
}

#[derive(Accounts)]
pub struct Swap<'info> {
    #[account(mut)]
    pub user: Signer<'info>,

    /// pool PDA, contains vault pubkeys
    #[account(
        seeds = [b"pool"],
        bump,
    )]
    pub pool: Account<'info, Pool>,

    /// User's ATA for YOUR_TOKEN
    #[account(mut, constraint = user_token_a.mint == token_a_mint.key())]
    pub user_token_a: Account<'info, TokenAccount>,

    /// User's ATA for WSOL
    #[account(mut, constraint = user_token_b.mint == token_b_mint.key())]
    pub user_token_b: Account<'info, TokenAccount>,

    /// Pool's vault for YOUR_TOKEN (must match pool.token_a_vault)
    #[account(mut, constraint = pool_token_a_vault.key() == pool.token_a_vault)]
    pub pool_token_a_vault: Account<'info, TokenAccount>,

    /// Pool's vault for WSOL (must match pool.token_b_vault)
    #[account(mut, constraint = pool_token_b_vault.key() == pool.token_b_vault)]
    pub pool_token_b_vault: Account<'info, TokenAccount>,

    /// Your token mint
    /// CHECK: used only to check user_token_a.mint constraint; not deserialized.
    pub token_a_mint: UncheckedAccount<'info>,

    /// WSOL mint
    /// CHECK: used only to check user_token_b.mint constraint; not deserialized.
    pub token_b_mint: UncheckedAccount<'info>,

    pub token_program: Program<'info, Token>,
}

#[account]
pub struct Pool {
    pub token_a_vault: Pubkey,
    pub token_b_vault: Pubkey,
}

#[error_code]
pub enum ErrorCode {
    #[msg("Calculation overflow")]
    CalculationOverflow,
    #[msg("Invalid amount for swap")]
    InvalidAmount,
    #[msg("Invalid PDA seeds / bump")]
    InvalidSeeds,
}

