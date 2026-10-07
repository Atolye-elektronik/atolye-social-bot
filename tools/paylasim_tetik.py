# -*- coding: utf-8 -*-
"""Zamani gelmis ama paylasilmamis post varsa "Sosyal medya paylasimi"ni hemen tetikler
(Windows gorevi AtolyePaylasimTetik, 10 dakikada bir).

07.10.2026 kullanici: "16 saattir Instagram'da paylasim yok". Sebep: publish.yml
yalniz 12:00 ve 20:30 TR cron'larinda donuyor ve GitHub bu cron'lari 3-5 saat
geciktiriyor (06.10 20:00 videosu 00:48'de, 19:30 postu 22:14'te gitti).
Nobetci ancak 90 dk tolerans dolunca ve cron anina gore bakiyordu. Bu tetik
postun kendi publish_at saatine bakar: saat geldiyse ve published.json'da
eksik platform varsa is akisini dakikalar icinde calistirir.

Mukerrer risk yok: publish kendisi fikirli (is_due + published.json).
Calisan/kuyrukta is varsa ya da son 20 dk icinde bir paylasim kosusu
baslamissa yenisini eklemez. Ayni post icin en fazla DENEME_SINIRI kez
tetikler (kalici hata veren platform her 10 dk'da kosu dogurmasin).
"""
import datetime as dt
import json
import pathlib
import re
import subprocess
import sys

DEPO = "Atolye-elektronik/atolye-social-bot"
KOK = pathlib.Path(__file__).resolve().parents[1]
DURUM = KOK / "state" / "paylasim_tetik.json"   # yerel, gitignore'daki state gibi
TR = dt.timezone(dt.timedelta(hours=3))
# Actions'ta publish.yml'nin gonderdigi platformlar (tiktok/tiktok_studio/pinterest_studio yerelde ya da ayri)
TAKIP = {"instagram", "facebook", "threads", "youtube"}
GERI_BAKIS = dt.timedelta(hours=36)
BEKLEME = dt.timedelta(minutes=20)
DENEME_SINIRI = 4


def calistir(*a, timeout=90):
    return subprocess.run(list(a), capture_output=True, text=True, encoding="utf-8", timeout=timeout, cwd=KOK)


def gh(*a):
    return calistir("gh", *a)


def main() -> int:
    kuru = "--kuru" in sys.argv          # test: tetiklemeden ne yapacagini yazar
    simdi = dt.datetime.now(TR)
    if "--simdi" in sys.argv:            # test: --simdi "2026-10-07 19:15"
        simdi = dt.datetime.strptime(sys.argv[sys.argv.index("--simdi") + 1], "%Y-%m-%d %H:%M").replace(tzinfo=TR)
    calistir("git", "fetch", "-q", "github", "main")
    yayin = json.loads(calistir("git", "show", "github/main:state/published.json").stdout or "{}")
    dosyalar = calistir("git", "ls-tree", "--name-only", "github/main", "posts/").stdout.split()

    eksik = []
    for yol in dosyalar:
        ad = pathlib.PurePosixPath(yol).name
        if not ad.endswith(".md") or ad[:10] < (simdi - GERI_BAKIS).strftime("%Y-%m-%d"):
            continue
        metin = calistir("git", "show", f"github/main:{yol}").stdout
        m = re.search(r"^publish_at:\s*(\d{4}-\d\d-\d\d \d\d:\d\d)", metin, re.M)
        p = re.search(r"^platforms:\s*\[(.*?)\]", metin, re.M)
        if not (m and p):
            continue
        zaman = dt.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M").replace(tzinfo=TR)
        if not (simdi - GERI_BAKIS <= zaman <= simdi):
            continue
        slug = ad[:-3]
        istenen = {x.strip() for x in p.group(1).split(",")} & TAKIP
        kalan = istenen - set(yayin.get(slug, {}))
        if kalan:
            eksik.append((slug, sorted(kalan)))

    if not eksik:
        print(f"{simdi:%d.%m %H:%M} bekleyen post yok")
        return 0

    try:
        durum = json.loads(DURUM.read_text(encoding="utf-8"))
    except Exception:
        durum = {}
    eksik = [(s, k) for s, k in eksik if durum.get(s, 0) < DENEME_SINIRI]
    if not eksik:
        print(f"{simdi:%d.%m %H:%M} eksik postlar deneme sinirini doldurdu, elle bakilmali")
        return 0

    r = gh("run", "list", "--repo", DEPO, "--workflow", "publish.yml", "-L", "5", "--json", "status,createdAt")
    kosular = json.loads(r.stdout or "[]")
    if any(k["status"] in ("queued", "in_progress", "waiting", "pending", "requested") for k in kosular):
        print(f"{simdi:%d.%m %H:%M} paylasim zaten calisiyor, atlandi")
        return 0
    if kosular:
        son = dt.datetime.fromisoformat(kosular[0]["createdAt"].replace("Z", "+00:00"))
        if simdi - son < BEKLEME:
            print(f"{simdi:%d.%m %H:%M} son kosu {int((simdi - son).total_seconds() // 60)} dk once, bekleniyor")
            return 0

    if kuru:
        print(f"{simdi:%d.%m %H:%M} [kuru] tetiklenecekti: " + "; ".join(f"{s} ({','.join(k)})" for s, k in eksik))
        return 0
    t = gh("workflow", "run", "publish.yml", "--repo", DEPO)
    for s, _ in eksik:
        durum[s] = durum.get(s, 0) + 1
    DURUM.write_text(json.dumps(durum, ensure_ascii=False, indent=1), encoding="utf-8")
    ozet = "; ".join(f"{s} ({','.join(k)})" for s, k in eksik)
    print(f"{simdi:%d.%m %H:%M} " + ("tetiklendi: " if t.returncode == 0 else "HATA " + (t.stderr or "")[:200] + " | ") + ozet)
    return t.returncode


if __name__ == "__main__":
    sys.exit(main())
