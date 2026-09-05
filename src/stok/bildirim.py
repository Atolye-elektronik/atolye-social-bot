# -*- coding: utf-8 -*-
"""Siparis / stok bildirimleri: Telegram + Google Sheet (Apps Script webhook).

Env:
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID   -> Telegram mesaji (yoksa sessizce atlar)
  STOK_SHEET_WEBHOOK                     -> Apps Script "Web App" URL'si; JSON POST ile satir ekler
                                            (yoksa atlar). Sheet tarafi: doPost(e) -> JSON.parse(e.postData.contents)
                                            -> sheet.appendRow([...])
Hicbiri tanimli degilse yalnizca stdout'a yazar; boylece kuru calistirmada da gorulur.
"""
import json
import os
from datetime import datetime

import requests


def telegram(metin):
    tok = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    cid = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not tok or not cid:
        return "telegram: token/chat yok"
    r = requests.post("https://api.telegram.org/bot%s/sendMessage" % tok,
                      json={"chat_id": cid, "text": metin[:4000], "parse_mode": "HTML",
                            "disable_web_page_preview": True}, timeout=30)
    return "telegram: %s" % r.status_code


def sheet(satirlar):
    """satirlar: [[tarih, kanal, siparisNo, kod, adet, dusum, not], ...]"""
    url = os.environ.get("STOK_SHEET_WEBHOOK", "").strip()
    if not url:
        return "sheet: webhook yok"
    r = requests.post(url, json={"rows": satirlar}, timeout=30)
    return "sheet: %s" % r.status_code


def siparis_bildir(yeni, dusum, kritik, kuru=True):
    """yeni: siparis.py'nin yeni siparis listesi; dusum: {parca: adet}; kritik: {kod: stok}."""
    if not yeni:
        return None
    an = datetime.now().strftime("%d.%m %H:%M")
    sat = []
    for o in yeni:
        for kl in o["kalemler"]:
            sat.append("• <b>%s</b> %s — %s x%d" % (o["kanal"], o["no"], kl.get("kod") or kl.get("barkod"), kl["adet"]))
    metin = "🛒 <b>%d yeni siparis</b> (%s)%s\n%s" % (len(yeni), an, " [KURU]" if kuru else "", "\n".join(sat[:40]))
    if dusum:
        metin += "\n\n📦 Parca dusumu: " + ", ".join("%s −%d" % (k, v) for k, v in sorted(dusum.items()))
    if kritik:
        metin += "\n\n⚠️ Kritik stok: " + ", ".join("%s=%s" % (k, v) for k, v in sorted(kritik.items()))
    print(metin)
    print(telegram(metin))
    rows = [[an, o["kanal"], o["no"], kl.get("kod") or kl.get("barkod"), kl["adet"],
             json.dumps(kl.get("dusum") or {}, ensure_ascii=False), "kuru" if kuru else ""]
            for o in yeni for kl in o["kalemler"]]
    print(sheet(rows))
    return metin


if __name__ == "__main__":
    print(telegram("Stok merkezi test mesaji ✅"))
