# -*- coding: utf-8 -*-
"""Idefix'te 'Atolye Elektronik' markasi olusana kadar bekler; olusunca 117 urunu basar.

Windows gorev zamanlayici ile saatlik calistirilir. Bir kez basinca
state/idefix_basildi.json yazar ve bir daha basmaz.
"""
import json
import os
import subprocess
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(KOK)
sys.path.insert(0, os.path.join(KOK, "src"))
for ln in open(".env", encoding="utf-8"):
    ln = ln.strip()
    if ln and not ln.startswith("#") and "=" in ln:
        k, v = ln.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"'))

from marketplaces import idefix_client as ix  # noqa: E402

DURUM = os.path.join(KOK, "state", "idefix_basildi.json")
LOG = os.path.join(KOK, "state", "idefix_marka_bekle.log")


def log(m):
    from datetime import datetime
    with open(LOG, "a", encoding="utf-8") as f:
        f.write("%s %s\n" % (datetime.now().strftime("%Y-%m-%d %H:%M"), m))
    print(m)


def main():
    if os.path.exists(DURUM):
        log("zaten basildi, cikiliyor"); return
    r = ix.get("/pim/brand/search-by-name", title="Atölye Elektronik")
    j = r.json() if r.status_code == 200 else []
    hit = [b for b in j if str(b.get("title", "")).strip().lower() in ("atölye elektronik", "atolye elektronik")]
    if not hit:
        log("marka henuz yok (%d sonuc)" % len(j)); return
    bid = hit[0]["id"]
    log("MARKA BULUNDU id=%s -> urunler basiliyor" % bid)
    env = dict(os.environ, IDEFIX_BRAND_ID=str(bid), PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, os.path.join(KOK, "src", "marketplaces", "idefix_urun_ekle.py"), "--gonder"],
                       capture_output=True, text=True, env=env, cwd=KOK)
    log(p.stdout[-1500:] + p.stderr[-800:])
    if "create -> 200" in p.stdout or '"batchRequestId"' in p.stdout:
        json.dump({"brandId": bid, "cikti": p.stdout[-1500:]}, open(DURUM, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        log("BASILDI")


if __name__ == "__main__":
    main()
