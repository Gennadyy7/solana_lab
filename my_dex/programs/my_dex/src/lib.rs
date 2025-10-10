use anchor_lang::prelude::*;
use anchor_spl::token::{self, Token, Transfer};

// Адрес твоего токена
declare_id!("mntrBoi14K4bn4QqT9pHicv3EKqvxCT4y9mS7YfJkDh");

// Курс: 1 WSOL = 2 твоих токена
const WSOL_TO_TOKEN_RATE: u64 = 2;

#[program]
pub mod my_dex {
    use super::*;

    pub fn initialize(ctx: Context<Initialize>) -> Result<()> {
        let pool = &mut ctx.accounts.pool;
        pool.token_a_vault = ctx.accounts.token_a_vault.key();
        pool.token_b_vault = ctx.accounts.token_b_vault.key();
        Ok(())
    }

    pub fn buy(ctx: Context<Swap>, amount_in: u64) -> Result<()> {
        let amount_out = amount_in
            .checked_mul(WSOL_TO_TOKEN_RATE)
            .ok_or(ErrorCode::CalculationOverflow)?;

        // Пользователь отправляет WSOL в пул
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

        // Пул отправляет твои токены пользователю
        token::transfer(
            CpiContext::new(
                ctx.accounts.token_program.to_account_info(),
                Transfer {
                    from: ctx.accounts.pool_token_a_vault.to_account_info(),
                    to: ctx.accounts.user_token_a.to_account_info(),
                    authority: ctx.accounts.pool_signer.to_account_info(),
                },
            ),
            amount_out,
        )?;

        Ok(())
    }

    pub fn sell(ctx: Context<Swap>, amount_in: u64) -> Result<()> {
        let amount_out = amount_in
            .checked_div(WSOL_TO_TOKEN_RATE)
            .ok_or(ErrorCode::InvalidAmount)?;

        // Пользователь отправляет твои токены в пул
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

        // Пул отправляет WSOL пользователю
        token::transfer(
            CpiContext::new(
                ctx.accounts.token_program.to_account_info(),
                Transfer {
                    from: ctx.accounts.pool_token_b_vault.to_account_info(),
                    to: ctx.accounts.user_token_b.to_account_info(),
                    authority: ctx.accounts.pool_signer.to_account_info(),
                },
            ),
            amount_out,
        )?;

        Ok(())
    }
}

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(mut)]
    pub user: Signer<'info>,

    #[account(
        init,
        payer = user,
        space = 8 + 32 + 32,
        seeds = [b"pool"],
        bump
    )]
    pub pool: Account<'info, Pool>,

    #[account(
        init,
        payer = user,
        token::mint = token_a_mint,
        token::authority = pool,
    )]
    pub token_a_vault: Account<'info, token::TokenAccount>,

    #[account(
        init,
        payer = user,
        token::mint = token_b_mint,
        token::authority = pool,
    )]
    pub token_b_vault: Account<'info, token::TokenAccount>,

    /// CHECK: Your token mint
    pub token_a_mint: UncheckedAccount<'info>,

    /// CHECK: WSOL mint
    pub token_b_mint: UncheckedAccount<'info>,

    pub system_program: Program<'info, System>,
    pub token_program: Program<'info, Token>,
}

#[derive(Accounts)]
pub struct Swap<'info> {
    #[account(mut)]
    pub user: Signer<'info>,

    #[account(
        seeds = [b"pool"],
        bump,
    )]
    pub pool: Account<'info, Pool>,

    /// CHECK: PDA signer for the pool
    #[account(
        seeds = [b"pool"],
        bump,
        signer
    )]
    pub pool_signer: UncheckedAccount<'info>,

    /// CHECK: User's ATA for your token
    #[account(mut)]
    pub user_token_a: UncheckedAccount<'info>,

    /// CHECK: User's ATA for WSOL
    #[account(mut)]
    pub user_token_b: UncheckedAccount<'info>,

    /// CHECK: Pool's ATA for your token
    #[account(mut)]
    pub pool_token_a_vault: UncheckedAccount<'info>,

    /// CHECK: Pool's ATA for WSOL
    #[account(mut)]
    pub pool_token_b_vault: UncheckedAccount<'info>,

    /// CHECK: Your token mint
    pub token_a_mint: UncheckedAccount<'info>,

    /// CHECK: WSOL mint
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
}
