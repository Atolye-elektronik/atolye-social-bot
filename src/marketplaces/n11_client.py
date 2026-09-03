"""N11 REST API istemcisi.

Anahtarlar: N11 Satici Paneli > Magazam > N11 Entegrasyon Bilgileri
sayfasindaki "App Key" ve "App Secret".
Ortam degiskenleri: N11_API_KEY, N11_API_SECRET
"""
from __future__ import annotations

import os

import requests

BASE_URL = "https://api.n11.com"
API_KEY = os.environ.get("N11_API_KEY", "").strip()
API_SECRET = os.environ.get("N11_API_SECRET", "").strip()
ENTEGRATOR = os.environ.get("N11_INTEGRATOR", "AtolyeElektronik")


def _basliklar() -> dict:
    if not API_KEY or not API_SECRET:
        raise SystemExit(
            "N11_API_KEY ve N11_API_SECRET tanimli olmali.\n"
            "N11 panelinde: Magazam > N11 Entegrasyon Bilgileri > App Key / App Secret"
        )
    return {
        "appkey": API_KEY,
        "appsecret": API_SECRET,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def get(yol: str, **params):
    r = requests.get(f"{BASE_URL}{yol}", headers=_basliklar(), params=params, timeout=60)
    return r


def post(yol: str, govde: dict):
    r = requests.post(f"{BASE_URL}{yol}", headers=_basliklar(), json=govde, timeout=90)
    return r
