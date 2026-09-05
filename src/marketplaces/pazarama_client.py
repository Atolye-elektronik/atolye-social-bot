"""Pazarama API istemcisi (OAuth2 client credentials).

Ortam degiskenleri: PAZARAMA_API_KEY, PAZARAMA_SECRET_KEY
"""
from __future__ import annotations

import base64
import os

import requests

TOKEN_URL = "https://isortagimgiris.pazarama.com/connect/token"
BASE_URL = "https://isortagimapi.pazarama.com"
API_KEY = os.environ.get("PAZARAMA_API_KEY", "").strip()
SECRET = os.environ.get("PAZARAMA_SECRET_KEY", "").strip()

_token = None


def token() -> str:
    global _token
    if _token:
        return _token
    if not API_KEY or not SECRET:
        raise SystemExit("PAZARAMA_API_KEY ve PAZARAMA_SECRET_KEY tanimli olmali.")
    kimlik = base64.b64encode(f"{API_KEY}:{SECRET}".encode()).decode()
    r = requests.post(
        TOKEN_URL,
        headers={"Authorization": f"Basic {kimlik}",
                 "Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "client_credentials",
              "scope": "merchantgatewayapi.fullaccess"},
        timeout=60,
    )
    r.raise_for_status()
    _token = r.json()["data"]["accessToken"]
    return _token


def _h() -> dict:
    return {"Authorization": f"Bearer {token()}", "Content-Type": "application/json"}


def get(yol: str, **params):
    return requests.get(f"{BASE_URL}{yol}", headers=_h(), params=params, timeout=60)


def post(yol: str, govde):
    return requests.post(f"{BASE_URL}{yol}", headers=_h(), json=govde, timeout=90)
