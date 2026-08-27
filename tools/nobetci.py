# -*- coding: utf-8 -*-
"""Nobetci: zamaninda calismayan is akislarini bulur ve kendisi tetikler.

Neden var: 26.08.2026'da GitHub Actions arizasi (15:02-17:40 UTC) sonrasi
depodaki TUM cron kayitlari takildi. 24 saat boyunca hicbir is calismadi ve
bunu fark eden otomasyon degil, kullanici oldu. Sessiz basarisizlik en kotu
basarisizlik.

Mantik: her is akisinin cron'undan "en son ne zaman calismasi gerekiyordu"
hesaplanir, GitHub'dan gercekten calisip calismadigina bakilir. Tolerans
suresini asmissa is workflow_dispatch ile tetiklenir.

Guvenli: paylasim islerinin kendisi zaten fikirli (is_due => publish_at <= now),
yani gec tetiklenen tur kaybolan gonderiyi telafi eder, mukerrer paylasim
yapmaz. Nobetci ayni isi tolerans penceresinde bir kez tetikler.

    python tools/nobetci.py            # sadece rapor
    python tools/nobetci.py --tetikle  # kacanlari calistir
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import subprocess
import sys

DEPO = "Atolye-elektronik/atolye-social-bot"
KOK = pathlib.Path(__file__).resolve().parents[1]
AKIS_DIZIN = KOK / ".github" / "workflows"
KAYIT = KOK / "state" / "nobetci.json"

# Cron'dan sonra ne kadar beklenir. Actions yogunlukta 30-60 dk gecikebiliyor,
# bu yuzden tolerans genis; aylik is icin cok daha genis.
VARSAYILAN_TOLERANS_DK = 90
TOLERANS_DK = {
    "threads-token.yml": 24 * 60,      # ayda bir, gecikmesi kritik degil
    "haftalik-rapor.yml": 6 * 60,      # haftalik
    "tiktok-zamanla.yml": 6 * 60,      # haftada iki
    "gitlab-yedek.yml": 6 * 60,        # gunluk yedek
}

# Nobetci kendini tetiklemesin.
HARIC = {"nobetci.yml"}


def gh(*args: str) -> str:
    r = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} basarisiz: {r.stderr.strip()[:300]}")
    return r.stdout


def cron_alanlari(ifade: str):
    """5 alanli cron'u dakika bazinda esleme kumelerine cevirir."""
    alanlar = ifade.split()
    if len(alanlar) != 5:
        raise ValueError(f"beklenmeyen cron: {ifade!r}")
    sinirlar = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 6)]
    kumeler = []
    for alan, (alt, ust) in zip(alanlar, sinirlar):
        kume = set()
        for parca in alan.split(","):
            adim = 1
            if "/" in parca:
                parca, adim_s = parca.split("/", 1)
                adim = int(adim_s)
            if parca == "*":
                bas, son = alt, ust
            elif "-" in parca:
                bas_s, son_s = parca.split("-", 1)
                bas, son = int(bas_s), int(son_s)
            else:
                bas = son = int(parca)
            kume.update(range(bas, son + 1, adim))
        kumeler.append(kume)
    return kumeler


def son_beklenen(ifade: str, simdi: dt.datetime) -> dt.datetime | None:
    """Cron'un simdiden onceki en son atesleme anini bulur (UTC)."""
    dk, sa, gun, ay, hafta = cron_alanlari(ifade)
    an = simdi.replace(second=0, microsecond=0)
    # En fazla 40 gun geriye bak (aylik isler icin yeterli).
    for _ in range(40 * 24 * 60):
        an -= dt.timedelta(minutes=1)
        if (an.minute in dk and an.hour in sa and an.day in gun
                and an.month in ay and (an.weekday() + 1) % 7 in hafta):
            return an
    return None


def akislari_oku():
    """Her is akisi dosyasi icin (dosya, ad, cron listesi, dispatch var mi)."""
    cikti = []
    for yol in sorted(AKIS_DIZIN.glob("*.yml")):
        if yol.name in HARIC:
            continue
        metin = yol.read_text(encoding="utf-8")
        # Yorum satirlarindaki cron ornekleri sayilmasin diye satir basi aranir.
        cronlar = re.findall(r'^\s*-\s*cron:\s*["\']([^"\']+)["\']', metin, re.MULTILINE)
        if not cronlar:
            continue
        ad_m = re.search(r"^name:\s*(.+)$", metin, re.MULTILINE)
        cikti.append({
            "dosya": yol.name,
            "ad": ad_m.group(1).strip() if ad_m else yol.stem,
            "cronlar": cronlar,
            "dispatch": "workflow_dispatch" in metin,
        })
    return cikti


def son_calisma(dosya: str) -> dt.datetime | None:
    ham = gh("run", "list", "--repo", DEPO, "--workflow", dosya,
             "--limit", "20", "--json", "createdAt,conclusion,status")
    for k in json.loads(ham or "[]"):
        # Devam eden veya basarili kosu "calisti" sayilir; basarisiz kosuyu
        # nobetci tekrar tetiklemez - o ayri bir sorun, ayri raporlanir.
        if k.get("status") != "completed" or k.get("conclusion") == "success":
            return dt.datetime.fromisoformat(k["createdAt"].replace("Z", "+00:00"))
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tetikle", action="store_true", help="kacan isleri calistir")
    a = ap.parse_args()

    simdi = dt.datetime.now(dt.timezone.utc)
    rapor, gecikenler = [], []

    for akis in akislari_oku():
        tolerans = TOLERANS_DK.get(akis["dosya"], VARSAYILAN_TOLERANS_DK)
        # Toleransi "en son beklenen an"a gore olcmek yanlisti: 2 saatte bir
        # donen bir iste tolerans dolmadan bir sonraki beklenen an geliyor ve
        # kacan tur asla yakalanmiyordu. Dogrusu, su ana kadar BITMIS OLMASI
        # GEREKEN son atesleme -- yani (simdi - tolerans) aninden onceki son
        # atesleme -- ile gercek kosuyu karsilastirmak.
        kesim = simdi - dt.timedelta(minutes=tolerans)
        beklenen = max(
            (b for b in (son_beklenen(c, kesim) for c in akis["cronlar"]) if b),
            default=None,
        )
        if beklenen is None:
            continue
        son = son_calisma(akis["dosya"])
        gecikme_dk = int((simdi - beklenen).total_seconds() // 60)
        kacti = son is None or son < beklenen

        rapor.append({
            "dosya": akis["dosya"], "ad": akis["ad"],
            "beklenen": beklenen.isoformat(),
            "son_calisma": son.isoformat() if son else None,
            "gecikme_dk": gecikme_dk, "kacti": kacti,
        })
        durum = "KACTI" if kacti else "tamam"
        son_s = son.strftime("%d.%m %H:%M") if son else "hic"
        print(f"{durum:6s} {akis['ad'][:34]:34s} beklenen {beklenen.strftime('%d.%m %H:%M')} UTC | son {son_s}")
        if kacti:
            gecikenler.append(akis)

    KAYIT.parent.mkdir(parents=True, exist_ok=True)
    KAYIT.write_text(json.dumps(
        {"kontrol": simdi.isoformat(), "akislar": rapor}, ensure_ascii=False, indent=2
    ), encoding="utf-8")

    if not gecikenler:
        print("\nHepsi zamaninda calismis.")
        return 0

    print(f"\n!! {len(gecikenler)} is zamaninda calismamis.")
    if not a.tetikle:
        print("Tetiklemek icin: --tetikle")
        return 1

    for akis in gecikenler:
        if not akis["dispatch"]:
            print(f"   {akis['dosya']}: workflow_dispatch yok, elle bakilmali")
            continue
        try:
            gh("workflow", "run", akis["dosya"], "--repo", DEPO)
            print(f"   tetiklendi: {akis['ad']}")
        except RuntimeError as e:
            print(f"   TETIKLENEMEDI {akis['dosya']}: {e}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
