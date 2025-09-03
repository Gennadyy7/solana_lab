from solders.keypair import Keypair


def main():
    keypair = Keypair()
    public_key = keypair.pubkey()
    # secret_key = list(keypair.to_bytes())

    print("=== Новый кошелёк создан ===")
    print(f"Публичный ключ (адрес): {public_key}")
    print(f"Приватный ключ (base58, кусок): {keypair.to_bytes()[:8].hex()}...")
    # print(f"Полный секретный ключ (список байтов): {secret_key}")


if __name__ == "__main__":
    main()
