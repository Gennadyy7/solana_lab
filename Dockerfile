FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    libssl-dev \
    pkg-config \
    libudev-dev \
    && rm -rf /var/lib/apt/lists/*

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

RUN sh -c "$(curl -sSfL https://release.anza.xyz/stable/install)" \
    && mv /root/.local/share/solana/install/active_release/bin/solana* /usr/local/bin/

RUN cargo install spl-token-cli

RUN pip install poetry==2.0.1
RUN poetry self add poetry-plugin-export

WORKDIR /app
COPY pyproject.toml poetry.lock ./

RUN poetry config virtualenvs.create false && \
    poetry export -f requirements.txt --output requirements.txt --without-hashes && \
    pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    libssl-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g ts-node typescript

WORKDIR /app
RUN npm init -y

RUN npm install \
    @solana/web3.js@latest \
    @raydium-io/raydium-sdk-v2@latest \
    @solana/spl-token@latest \
    bn.js@latest \
    decimal.js@latest \
    @types/bn.js@latest \
    bs58@latest \
    dotenv@latest \
    typescript@latest \
    ts-node@latest \
    @types/node@latest

COPY --from=builder /usr/local/bin/solana* /usr/local/bin/
COPY --from=builder /root/.cargo/bin/spl-token /usr/local/bin/spl-token
COPY --from=builder /usr/local/lib/python3.12/site-packages/ /usr/local/lib/python3.12/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH="/usr/local/bin:${PATH}"

COPY scripts/ ./scripts/

RUN solana config set --url http://solana-validator:8899
RUN solana-keygen new --no-passphrase --outfile /root/.config/solana/id.json

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8899 8900 8000-8009

ENTRYPOINT ["/entrypoint.sh"]
CMD ["tail", "-f", "/dev/null"]