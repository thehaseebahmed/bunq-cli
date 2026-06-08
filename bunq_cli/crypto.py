import base64

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import load_pem_private_key


def generate_key_pair() -> tuple[str, str]:
    """Return (private_pem, public_pem) for a fresh RSA-2048 key pair."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return private_pem, public_pem


def sign(private_pem: str, data: bytes) -> str:
    """Sign *data* and return the Base64-encoded signature."""
    key = load_pem_private_key(private_pem.encode(), password=None)
    raw = key.sign(data, padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(raw).decode()
