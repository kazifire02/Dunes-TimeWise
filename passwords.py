"""Verify existing Werkzeug hashes on CPython and Python Workers alike."""

import hashlib
import hmac

from werkzeug.security import check_password_hash as werkzeug_check


def check_password_hash(stored, password):
    try:
        method, salt, expected = stored.split("$", 2)
        kind, *options = method.split(":")
        if kind == "pbkdf2" and not hasattr(hashlib, "pbkdf2_hmac"):
            # Workers' Python hashlib omits OpenSSL KDFs. PyCryptodome supplies
            # the same algorithms in WebAssembly, preserving existing hashes.
            from Crypto.Hash import SHA1, SHA256, SHA512
            from Crypto.Protocol.KDF import PBKDF2

            hashes = {"sha1": SHA1, "sha256": SHA256, "sha512": SHA512}
            algorithm = options[0] if options else "sha256"
            iterations = int(options[1]) if len(options) > 1 else 1_000_000
            digest = PBKDF2(
                password.encode(), salt.encode(), dkLen=len(bytes.fromhex(expected)),
                count=iterations, hmac_hash_module=hashes[algorithm],
            ).hex()
            return hmac.compare_digest(digest, expected)
        if kind == "scrypt" and not hasattr(hashlib, "scrypt"):
            from Crypto.Protocol.KDF import scrypt

            n, r, p = map(int, options) if options else (32768, 8, 1)
            digest = scrypt(password.encode(), salt.encode(), 64, n, r, p).hex()
            return hmac.compare_digest(digest, expected)
        return werkzeug_check(stored, password)
    except (ValueError, TypeError, KeyError):
        return False
