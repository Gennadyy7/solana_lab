use anchor_lang::prelude::*;
use anchor_spl::token::{self, Mint, Token, TokenAccount, Transfer};

declare_id!("2JubASqT22dDF7uPzZGtwqerKf6f8FhCms694yssT1ay"); // ✅ ровно 32 байта

#[program]
pub mod my_dex {
    use super::*;

    pub fn initialize(ctx: Context<Initialize>, rate: u64) -> Result<()> {
        let pool = &mut ctx.accounts.pool;
        pool.token_a_mint = ctx.accounts.token_a_mint.key();
        pool.token_b_mint = ctx.accounts.token_b_mint.key();
        pool.token_a_vault = ctx.accounts.token_a_vault.key();
        pool.token_b_vault = ctx.accounts.token_b_vault.key();
        pool.bump = ctx.bumps.pool;
        pool.rate = rate;
        Ok(())
    }

    pub fn buy(ctx: Context<Buy>, amount_b: u64) -> Result<()> {
        let pool = &ctx.accounts.pool;

        let seeds = &[
            b"pool",
            pool.token_a_mint.as_ref(),
            pool.token_b_mint.as_ref(),
            &[pool.bump],
        ];
        let signer_seeds = &[&seeds[..]];

        let amount_a = amount_b * 2; // фиксированный курс

        // Перевод WSOL от пользователя в пул
        let cpi_accounts_b = Transfer {
            from: ctx.accounts.user_b_ata.to_account_info(),
            to: ctx.accounts.token_b_vault.to_account_info(),
            authority: ctx.accounts.user.to_account_info(),
        };
        let cpi_ctx_b = CpiContext::new(ctx.accounts.token_program.to_account_info(), cpi_accounts_b);
        token::transfer(cpi_ctx_b, amount_b)?;

        // Перевод токена A из пула пользователю
        let cpi_accounts_a = Transfer {
            from: ctx.accounts.token_a_vault.to_account_info(),
            to: ctx.accounts.user_a_ata.to_account_info(),
            authority: ctx.accounts.pool.to_account_info(),
        };
        let cpi_ctx_a = CpiContext::new_with_signer(
            ctx.accounts.token_program.to_account_info(),
            cpi_accounts_a,
            signer_seeds,
        );
        token::transfer(cpi_ctx_a, amount_a)?;

        Ok(())
    }

    pub fn sell(ctx: Context<Sell>, amount_a: u64) -> Result<()> {
        let pool = &ctx.accounts.pool;

        let seeds = &[
            b"pool",
            pool.token_a_mint.as_ref(),
            pool.token_b_mint.as_ref(),
            &[pool.bump],
        ];
        let signer_seeds = &[&seeds[..]];

        let amount_b = amount_a / 2; // фиксированный курс

        // Перевод токена A от пользователя в пул
        let cpi_accounts_a = Transfer {
            from: ctx.accounts.user_a_ata.to_account_info(),
            to: ctx.accounts.token_a_vault.to_account_info(),
            authority: ctx.accounts.user.to_account_info(),
        };
        let cpi_ctx_a = CpiContext::new(ctx.accounts.token_program.to_account_info(), cpi_accounts_a);
        token::transfer(cpi_ctx_a, amount_a)?;

        // Перевод WSOL из пула пользователю
        let cpi_accounts_b = Transfer {
            from: ctx.accounts.token_b_vault.to_account_info(),
            to: ctx.accounts.user_b_ata.to_account_info(),
            authority: ctx.accounts.pool.to_account_info(),
        };
        let cpi_ctx_b = CpiContext::new_with_signer(
            ctx.accounts.token_program.to_account_info(),
            cpi_accounts_b,
            signer_seeds,
        );
        token::transfer(cpi_ctx_b, amount_b)?;

        Ok(())
    }
}

#[derive(Accounts)]
#[instruction(rate: u64)]
pub struct Initialize<'info> {
    #[account(
        init,
        payer = user,
        space = 8 + 32*4 + 8 + 1,
        seeds = [b"pool", token_a_mint.key().as_ref(), token_b_mint.key().as_ref()],
        bump
    )]
    pub pool: Account<'info, PoolState>,

    #[account(mut)]
    pub token_a_mint: Account<'info, Mint>,
    #[account(mut)]
    pub token_b_mint: Account<'info, Mint>,

    #[account(
        mut,
        constraint = token_a_vault.mint == token_a_mint.key(),
        constraint = token_b_vault.mint == token_b_mint.key(),
    )]
    pub token_a_vault: Account<'info, TokenAccount>,
    pub token_b_vault: Account<'info, TokenAccount>,

    #[account(mut)]
    pub user: Signer<'info>,

    pub system_program: Program<'info, System>,
    pub token_program: Program<'info, Token>,
    pub rent: Sysvar<'info, Rent>,
}

#[derive(Accounts)]
pub struct Buy<'info> {
    #[account(mut, has_one = token_a_vault, has_one = token_b_vault)]
    pub pool: Account<'info, PoolState>,

    #[account(mut)]
    pub user: Signer<'info>,

    #[account(mut)]
    pub user_a_ata: Account<'info, TokenAccount>,
    #[account(mut)]
    pub user_b_ata: Account<'info, TokenAccount>,

    #[account(mut)]
    pub token_a_vault: Account<'info, TokenAccount>,
    #[account(mut)]
    pub token_b_vault: Account<'info, TokenAccount>,

    pub token_program: Program<'info, Token>,
}

#[derive(Accounts)]
pub struct Sell<'info> {
    #[account(mut, has_one = token_a_vault, has_one = token_b_vault)]
    pub pool: Account<'info, PoolState>,

    #[account(mut)]
    pub user: Signer<'info>,

    #[account(mut)]
    pub user_a_ata: Account<'info, TokenAccount>,
    #[account(mut)]
    pub user_b_ata: Account<'info, TokenAccount>,

    #[account(mut)]
    pub token_a_vault: Account<'info, TokenAccount>,
    #[account(mut)]
    pub token_b_vault: Account<'info, TokenAccount>,

    pub token_program: Program<'info, Token>,
}

#[account]
pub struct PoolState {
    pub token_a_mint: Pubkey,
    pub token_b_mint: Pubkey,
    pub token_a_vault: Pubkey,
    pub token_b_vault: Pubkey,
    pub rate: u64,
    pub bump: u8,
}

