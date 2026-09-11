# -*- coding: utf-8 -*-
"""Gunluk e-posta turu — Windows Gorev Zamanlayici bu betigi her sabah calistirir.

Sirayla:
  1. Gunluk kota kontrolu (ayni gun ikinci kez calisirsa atlar)
  2. 15 MTAL + 10 MESEM gonderimi (info@, kayit defteriyle, Sent kopyali)
  3. info@ kutusundaki yeni iletileri Gmail'e aktar
  4. Gunun ozetini Gmail'e mail olarak dusur
  5. Kayit dosyalarini git'e isle ve GitHub'a gonder

Claude'a ya da sohbete bagli degil; bilgisayar o saatte acik ve oturum
acik olsun yeter. Kota: gunde 25 (spam itibari icin bilerek dusuk).

    python tools/gunluk_tur.py            # normal
    python tools/gunluk_tur.py --zorla    # ayni gun tekrar calistir
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import smtplib
import subprocess
import sys
import time
from email.message import EmailMessage
from email.utils import formatdate

KOK = pathlib.Path(__file__).resolve().parent.parent
os.chdir(KOK)
sys.path.insert(0, str(KOK))
for k in ("SMTP_USER", "SMTP_PASSWORD", "SMTP_HOST", "SMTP_PORT", "IMZA_ADI"):
    os.environ.pop(k, None)

from src import okul_daveti  # noqa: E402

PY = sys.executable
KOTA_DOSYA = KOK / "state/gunluk_tur.json"
KILIT_DOSYA = KOK / "state/gunluk_tur.lock"
# Kota ancak tur BITINCE yaziliyor; o yuzden kota kontrolu ayni anda baslayan
# ikinci turu durdurmuyor. 07.09.2026'da nobetci, elle baslatilan turun uzerine
# ikinci tur acti ve ayni okullara ikinci kez mail gitti. Kilit bunu engelliyor.
KILIT_OMRU = 2 * 60 * 60  # gorevin ExecutionTimeLimit degeri ile ayni
LOG_DIR = KOK / "logs/gunluk_tur"
MTAL_LISTE, MESEM_LISTE = "pazarlama/okullar-hedef.csv", "pazarlama/mesem-hedef.csv"
MTAL_ADET, MESEM_ADET = 15, 10
GMAIL = "atolyeelektronik07@gmail.com"


def log(msg: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    satir = f"[{dt.datetime.now():%H:%M:%S}] {msg}"
    # Log dosyasi utf-8 ama Windows konsolu cp1254; kodlanamayan karakter
    # print()'i patlatiyor. 09.09.2026'da kutu aktarim ciktisindaki bir karakter
    # yuzunden tur, ozet maili ve git adimlarina gelmeden coktu (25 mail gitmisti).
    kodlama = getattr(sys.stdout, "encoding", None) or "ascii"
    print(satir.encode(kodlama, errors="replace").decode(kodlama, errors="replace"))
    with (LOG_DIR / f"{dt.date.today()}.log").open("a", encoding="utf-8") as f:
        f.write(satir + "\n")


def kayit_oku() -> list[dict]:
    try:
        return json.loads(okul_daveti.STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def ozet_mail(gonderilen: list[str], kutu_cikti: str, gun: str) -> None:
    okul_daveti._env_dosyasini_yukle()
    kul, sif, host = os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"], os.environ["SMTP_HOST"]
    m = EmailMessage()
    m["Subject"] = f"Gunluk tur {gun} — {len(gonderilen)} okula gonderildi"
    # Gmail info@'yu kendi adresi sayip yutuyor; baslik farkli, zarf info@.
    m["From"] = "Gunluk tur <kutu-aktarimi@atolyeelektronik.com>"
    m["To"] = GMAIL
    m["Date"] = formatdate(localtime=True)
    govde = [f"Gonderen: {kul}", f"Tarih: {gun}", "",
             f"Gonderilen okullar ({len(gonderilen)}):"]
    govde += [f"  {i:2}. {o}" for i, o in enumerate(gonderilen, 1)]
    govde += ["", "Kutu kontrolu:", kutu_cikti.strip() or "  (cikti yok)"]
    m.set_content("\n".join(govde) + "\n")
    with smtplib.SMTP_SSL(host, 465, timeout=60) as s:
        s.login(kul, sif)
        s.send_message(m, from_addr=kul)


def _kilit_sahibi() -> int | None:
    """Kilit dosyasindaki pid; okunamazsa None."""
    try:
        return int(KILIT_DOSYA.read_text(encoding="utf-8").split()[0])
    except (OSError, ValueError, IndexError):
        return None


def _surec_yasiyor(pid: int) -> bool:
    """pid hala calisiyor mu. Windows'ta os.kill(pid, 0) SURECI OLDURUYOR
    (TerminateProcess cagiriyor), o yuzden tasklist ile bakiyoruz.
    11.09.2026'da tur disaridan oldurulup (0x8007042B) kilidi ortada
    biraktigi ve sonraki 2 saat tum turlari engelledigi icin eklendi."""
    try:
        r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                           capture_output=True, text=True, timeout=15)
        return str(pid) in (r.stdout or "")
    except Exception:
        return True  # emin olamiyorsak kilide saygi duy


def main() -> int:
    zorla = "--zorla" in sys.argv
    gun = str(dt.date.today())
    kota = {}
    if KOTA_DOSYA.exists():
        kota = json.loads(KOTA_DOSYA.read_text(encoding="utf-8"))
    if kota.get(gun) and not zorla:
        log(f"{gun} icin tur zaten yapilmis ({kota[gun]} gonderim); atlaniyor.")
        return 0

    if KILIT_DOSYA.exists():
        yas = time.time() - KILIT_DOSYA.stat().st_mtime
        sahip = _kilit_sahibi()
        if sahip and _surec_yasiyor(sahip) and yas < KILIT_OMRU:
            log(f"baska bir tur {yas/60:.0f} dk once baslamis (pid {sahip}), hala calisiyor; atlaniyor.")
            return 0
        if sahip and not _surec_yasiyor(sahip):
            log(f"olu kilit: pid {sahip} artik yok, yok sayiliyor.")
        else:
            log(f"bayat kilit bulundu ({yas/3600:.1f} sa), yok sayiliyor.")
    KILIT_DOSYA.parent.mkdir(parents=True, exist_ok=True)
    KILIT_DOSYA.write_text(f"{os.getpid()} {dt.datetime.now():%Y-%m-%d %H:%M:%S}", encoding="utf-8")

    try:
        return _tur(gun, kota)
    finally:
        KILIT_DOSYA.unlink(missing_ok=True)


def _tur(gun: str, kota: dict) -> int:
    log("gunluk tur basliyor")
    once = {k["ozet"] for k in kayit_oku()}

    toplam = 0
    for liste, adet, sablon in ((MTAL_LISTE, MTAL_ADET, "mtal"), (MESEM_LISTE, MESEM_ADET, "mesem")):
        if not (KOK / liste).exists():
            log(f"liste yok, atlandi: {liste}")
            continue
        try:
            n = okul_daveti.calistir(pathlib.Path(liste), limit=adet, sablon=sablon)
            log(f"{sablon}: {n} gonderildi")
            toplam += n
        except Exception as hata:
            log(f"{sablon} HATA: {hata}")

    gonderilen = [k["okul"] for k in kayit_oku() if k["ozet"] not in once]

    kota[gun] = toplam
    KOTA_DOSYA.write_text(json.dumps(kota, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    kutu = subprocess.run([PY, "tools/kutu_aktar.py", "--yeni"], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    log("kutu: " + (kutu.stdout.strip().replace("\n", " | ") or kutu.stderr.strip()[-200:]))

    try:
        ozet_mail(gonderilen, kutu.stdout, gun)
        log("ozet maili gonderildi")
    except Exception as hata:
        log(f"ozet maili HATA: {hata}")

    try:
        subprocess.run(["git", "add", "state/"], check=True, capture_output=True)
        subprocess.run(["git", "-c", "user.name=Atolye Elektronik", "-c", "user.email=bot@atolyeelektronik.com",
                        "commit", "-q", "-m", f"chore: {gun} gunluk tur - {toplam} okul"], capture_output=True)
        subprocess.run(["git", "push", "-q"], capture_output=True, timeout=120)
        log("git: kayit islendi ve gonderildi")
    except Exception as hata:
        log(f"git HATA: {hata}")

    log(f"tur bitti: {toplam} gonderim")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
