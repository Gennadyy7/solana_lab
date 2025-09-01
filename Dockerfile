# Этап 1: Сборка зависимостей
FROM python:3.12-slim AS builder

# Устанавливаем зависимости для Rust и Solana CLI
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    libssl-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем Rust
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Устанавливаем Solana CLI
RUN sh -c "$(curl -sSfL https://release.anza.xyz/stable/install)" \
    && mv /root/.local/share/solana/install/active_release/bin/solana* /usr/local/bin/

# Устанавливаем Poetry и зависимости Python
RUN pip install poetry==2.0.1
RUN poetry self add poetry-plugin-export

WORKDIR /app
COPY pyproject.toml poetry.lock ./

# Экспортируем зависимости и устанавливаем их
RUN poetry config virtualenvs.create false && \
    poetry export -f requirements.txt --output requirements.txt --without-hashes && \
    pip install --no-cache-dir -r requirements.txt

# Этап 2: Финальный образ
FROM python:3.12-slim

# Устанавливаем минимальные зависимости для работы Solana CLI
RUN apt-get update && apt-get install -y \
    libssl-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Копируем Solana CLI и Python-зависимости из builder
COPY --from=builder /usr/local/bin/solana* /usr/local/bin/
COPY --from=builder /usr/local/lib/python3.12/site-packages/ /usr/local/lib/python3.12/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# Настраиваем окружение Python
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH="/root/.local/share/solana/install/active_release/bin:${PATH}"

# Создаём рабочую директорию
WORKDIR /app

# Копируем скрипты
COPY scripts/ ./scripts/

# Настраиваем Solana CLI
RUN solana config set --url http://solana-validator:8899
RUN solana-keygen new --no-passphrase --outfile /root/.config/solana/id.json

# Копируем entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Открываем порты (на всякий случай)
EXPOSE 8899 8900 8000-8009

# Входная точка
ENTRYPOINT ["/entrypoint.sh"]
CMD ["tail", "-f", "/dev/null"]