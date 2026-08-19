"""PKCE (RFC 7636) helpers for the Sign in with Spoo device-auth flow."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import secrets
from typing import Any, NamedTuple


class PkcePair(NamedTuple):
    verifier: str
    challenge: str


def _base64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def generate_pkce_pair() -> PkcePair:
    """A fresh S256 verifier/challenge pair (verifier: 32 random bytes, 43 chars)."""
    verifier = _base64url(secrets.token_bytes(32))
    challenge = _base64url(hashlib.sha256(verifier.encode("ascii")).digest())
    return PkcePair(verifier=verifier, challenge=challenge)


def generate_state() -> str:
    """An unguessable state value for CSRF protection (16 random bytes)."""
    return _base64url(secrets.token_bytes(16))


def decode_jwt_payload(token: str) -> dict[str, Any] | None:
    """Decode a JWT payload WITHOUT verifying the signature.

    Only used to read ``exp`` for proactive refresh scheduling; never trust
    these claims for anything security-relevant.
    """
    try:
        payload = token.split(".")[1]
        padded = payload + "=" * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode(padded)
        parsed = json.loads(decoded)
    except (IndexError, ValueError, binascii.Error):
        return None
    return parsed if isinstance(parsed, dict) else None
