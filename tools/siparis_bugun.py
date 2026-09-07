# -*- coding: utf-8 -*-
"""Bugun gelen siparisler -> Desktop\SIPARIS-BUGUN.xlsx. Windows gorevi AtolyeSiparisBugun her gun 14:00.
Iki .env dosyasini (masaustu repo: HB kimlikleri; atolye-temiz: diger kanallar) kendisi yukler."""
import os, sys, pathlib
KOK = pathlib.Path(__file__).resolve().parents[1]
for env in (pathlib.Path(r"C:\Users\serdar\Desktop\atolyesocialbotmasaustu\.env"), KOK / ".env"):
    if env.exists():
        for l in env.read_text(encoding="utf-8", errors="ignore").splitlines():
            l = l.strip()
            if l and not l.startswith("#") and "=" in l:
                k, v = l.split("=", 1); os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
sys.path[:0] = [str(KOK / "src"), str(KOK / "src" / "marketplaces")]
from stok import siparis  # noqa: E402
siparis.liste(list(siparis.TOPLAYICI), str(pathlib.Path.home() / "Desktop" / "SIPARIS-BUGUN.xlsx"), sadece_bugun=True)
