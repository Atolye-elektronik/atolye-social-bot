# -*- coding: utf-8 -*-
"""Stok/siparis is akisini 5 dakikada bir UYGULA modunda tetikler (Windows gorevi AtolyeStokTetik).

02.10.2026: GitHub'in */15 cron'u pratikte saatlerce atlaniyor; nobetci.py ise
is akisini girdisiz tetikliyordu, bu da inputs.mod varsayilani "kuru" demekti
(siparisler dusulmuyordu). Kullanici "stok takibini 5 dakikaya dusur" dedi.

Kuyrukta ya da calisan bir is varsa yenisini eklemez (ust uste yigilmasin).
"""
import json, subprocess, sys

DEPO = "Atolye-elektronik/atolye-social-bot"

def gh(*a):
    return subprocess.run(["gh", *a], capture_output=True, text=True, encoding="utf-8", timeout=60)

r = gh("run", "list", "--repo", DEPO, "--workflow", "stok-siparis.yml", "-L", "5", "--json", "status")
try:
    aktif = [x for x in json.loads(r.stdout or "[]") if x.get("status") in ("queued", "in_progress", "waiting", "pending")]
except Exception:
    aktif = []
if aktif:
    print("zaten calisan/bekleyen is var, atlandi"); sys.exit(0)
t = gh("workflow", "run", "stok-siparis.yml", "--repo", DEPO, "-f", "mod=uygula")
print("tetiklendi" if t.returncode == 0 else "HATA: " + (t.stderr or "")[:300])
sys.exit(t.returncode)
