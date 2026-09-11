"""PttAVM Integration API istemcisi (self entegrator).

Taban: https://integration-api.pttavm.com/api/v1
Basliklar: Api-Key, Access-Token (panel > Hesap Yonetimi > Entegrasyon Bilgileri), Content-Type,
X-Correlation-Id (her istekte farkli uuid4). Yanlis yol 404/503 verir.
"""
from __future__ import annotations

import os
import uuid

import requests

BASE = "https://integration-api.pttavm.com/api/v1"


def _h() -> dict:
    key = os.environ.get("PTTAVM_API_KEY", "").strip()
    tok = os.environ.get("PTTAVM_ACCESS_TOKEN", "").strip().strip('"')
    if not key or not tok:
        raise RuntimeError("PTTAVM_API_KEY / PTTAVM_ACCESS_TOKEN eksik (atolye-temiz/.env)")
    return {"Api-Key": key, "Access-Token": tok, "Content-Type": "application/json",
            "X-Correlation-Id": str(uuid.uuid4())}


def get(yol: str, **params):
    return requests.get(BASE + yol, headers=_h(), params=params, timeout=60)


def post(yol: str, govde):
    return requests.post(BASE + yol, headers=_h(), json=govde, timeout=60)


def put(yol: str, govde):
    return requests.put(BASE + yol, headers=_h(), json=govde, timeout=60)
