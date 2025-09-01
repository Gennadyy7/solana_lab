#!/bin/bash

echo "Waiting for validator at http://solana-validator:8899..."
while ! curl -s http://solana-validator:8899 > /dev/null; do
    sleep 1
done
echo "Validator is up!"

exec "$@"