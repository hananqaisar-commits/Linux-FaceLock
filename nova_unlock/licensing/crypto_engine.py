"""Runtime-only license verification and local storage protection."""
import base64 as _b64
import hashlib as _h
import json as _js

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

# This is a public verification key, safe to distribute with the application.
# The matching private signing key is deliberately not present in this package.
_PUBLIC_KEY_B64 = "L8+Sx333NPnVQtiZ8mxqrCqey/wuSHjXjuXEiuApBqM="
_LICENSE_FORMAT = "nova-ed25519-v2"


def canonical_license_data(data):
    """Stable bytes signed by the operator and verified by the runtime."""
    return _js.dumps(data, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False).encode("utf-8")


def verify_license(data, signature):
    """Verify an Ed25519 signature. No signing capability exists in releases."""
    try:
        public_key = Ed25519PublicKey.from_public_bytes(
            _b64.b64decode(_PUBLIC_KEY_B64, validate=True))
        public_key.verify(_b64.b64decode(signature, validate=True),
                          canonical_license_data(data))
        return True
    except Exception:
        return False


def _storage_key():
    # This key protects local-at-rest data from casual inspection only. It is
    # not an authority key and cannot create a valid license.
    return _h.sha256(b"NovaUnlock local storage v2").digest()[:16]


def encrypt_data(data):
    key = _storage_key()
    result = [c ^ key[i % len(key)] for i, c in enumerate(data.encode())]
    return _b64.b64encode(bytes(result)).decode()


def decrypt_data(data):
    key = _storage_key()
    decoded = _b64.b64decode(data)
    return bytes(c ^ key[i % len(key)] for i, c in enumerate(decoded)).decode()
