# -*- coding: utf-8 -*-
"""Idefix satici API istemcisi.

Kimlik dogrulama Trendyol'daki gibi DEGIL: tek baslik
``X-API-KEY: base64(ApiKey:ApiSecret)``. Yanlis baslikta 401,
yanlis yol on ekinde 404 degil 503 doner.
"""
import base64
import os

import requests

BASE_URL = "https://merchantapi.idefix.com"
API_KEY = os.environ.get("IDEFIX_API_KEY", "").strip()
SECRET = os.environ.get("IDEFIX_SECRET", "").strip()
SATICI_ID = os.environ.get("IDEFIX_SATICI_ID", "").strip()


def _h() -> dict:
    jeton = base64.b64encode(("%s:%s" % (API_KEY, SECRET)).encode()).decode()
    return {"X-API-KEY": jeton, "Content-Type": "application/json"}


def get(yol: str, **params):
    return requests.get(BASE_URL + yol, headers=_h(), params=params, timeout=60)


def post(yol: str, govde):
    return requests.post(BASE_URL + yol, headers=_h(), json=govde, timeout=60)
