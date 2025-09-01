#!/bin/bash
# entrypoint.sh

# Проверяем, что валидатор доступен
echo "Waiting for validator at http://solana-validator:8899..."
while ! curl -s http://solana-validator:8899 > /dev/null; do
    sleep 1
done
echo "Validator is up!"

# Выполняем переданную команду
exec "$@"