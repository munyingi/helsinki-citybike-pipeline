"""Create an RSA key pair for the Snowflake service user (works on Windows, macOS, Linux).

Usage:
    python scripts/make_keypair.py

Writes:
    keys/rsa_key.p8   private key (never commit this; keys/ is in .gitignore)
    keys/rsa_key.pub  public key
and prints the ALTER USER statement to run in Snowsight.
"""
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

KEY_DIR = Path(__file__).resolve().parents[1] / "keys"


def main() -> None:
    KEY_DIR.mkdir(exist_ok=True)
    private_path = KEY_DIR / "rsa_key.p8"
    public_path = KEY_DIR / "rsa_key.pub"
    if private_path.exists():
        raise SystemExit(f"{private_path} already exists. Delete it first if you really want new keys.")

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    public_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    public_path.write_bytes(public_pem)

    body = "".join(line for line in public_pem.decode().splitlines() if "-----" not in line)
    print(f"Private key: {private_path}")
    print(f"Public key:  {public_path}\n")
    print("Run this in Snowsight as ACCOUNTADMIN:\n")
    print(f"ALTER USER dbt_user SET RSA_PUBLIC_KEY = '{body}';")


if __name__ == "__main__":
    main()
