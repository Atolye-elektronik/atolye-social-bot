# -*- coding: utf-8 -*-
"""info@ kutusundaki iletileri 07 Gmail'ine kopyalar (remail).

Neden var: info@ Guzel Hosting'de barinyor ve kimse o kutuyu acmiyor.
cPanel ileticisi kurulamadi, Gmail'in ice aktarmasi da self-signed
sertifika yuzunden sunucuyu reddediyor. Bu arac IMAP ile kutuyu okuyup
her iletiyi yeni bir zarf icinde 07 Gmail'ine gonderir — okul cevaplari
boylece zaten bakilan kutuya duser.

Gunluk e-posta gonderim turunda calistirilir:

    python tools/kutu_aktar.py            # tum INBOX
    python tools/kutu_aktar.py --yeni     # yalnizca okunmamislar (gunluk mod)

--yeni okunanlari atlar; aktarilan iletiler IMAP'te okundu isaretlenir,
boylece ayni ileti iki kez tasinmaz.
"""
import email, imaplib, os, smtplib, sys
from email.header import decode_header
from email.message import EmailMessage
sys.path.insert(0, ".")
for k in ("SMTP_USER","SMTP_PASSWORD","SMTP_HOST","SMTP_PORT","IMZA_ADI"):
    os.environ.pop(k, None)
from src.okul_daveti import _env_dosyasini_yukle
_env_dosyasini_yukle()
KUL, SIF = os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"]
HOST = os.environ["SMTP_HOST"]

def coz(m, h):
    p = decode_header(m.get(h, "") or "")
    return " ".join(x.decode(c or "utf-8", "replace") if isinstance(x, bytes) else x for x, c in p)

import argparse
ap = argparse.ArgumentParser()
ap.add_argument("--yeni", action="store_true", help="yalnizca okunmamislari aktar")
args = ap.parse_args()

M = imaplib.IMAP4_SSL(HOST, 993); M.login(KUL, SIF); M.select("INBOX")
_, veri = M.search(None, "UNSEEN" if args.yeni else "ALL")
idler = veri[0].split()
print(f"kutuda {len(idler)} ileti; aktariliyor...")

with smtplib.SMTP_SSL(HOST, 465, timeout=60) as S:
    S.login(KUL, SIF)
    for i in idler:
        _, d = M.fetch(i, "(BODY.PEEK[])")
        org = email.message_from_bytes(d[0][1])
        kimden, konu = coz(org, "From"), coz(org, "Subject") or "(konusuz)"
        gvd = ""
        for p in org.walk():
            if p.get_content_type() == "text/plain":
                gvd = p.get_payload(decode=True).decode(p.get_content_charset() or "utf-8", "replace")
                break
        y = EmailMessage()
        # Okul cevaplari hep @meb.k12.tr'den gelir; Gmail'de bir bakista
        # ayrilsin diye konu onekine [OKUL] ekleniyor. Digerleri cogunlukla
        # magaza adresine gelen soguk-satis spam'i.
        etiket = "[OKUL CEVABI]" if "meb.k12.tr" in kimden.lower() else "[info@ kutusu]"
        y["Subject"] = f"{etiket} {konu}"
        # Gonderen basligi bilerek info@ DEGIL: Gmail'de info@ "send as"
        # adresi olarak kayitli ve Gmail kendi adresinden gelen postayi
        # gelen kutusuna koymuyor (sessizce yutuyor). Zarf info@ kaliyor
        # (SPF), baslik farkli — eslesme kirilinca teslim normallesiyor.
        y["From"] = "info@ kutusu <kutu-aktarimi@atolyeelektronik.com>"
        y["Reply-To"] = coz(org, "From") or KUL
        y["To"] = "atolyeelektronik07@gmail.com"
        y.set_content(f"Orijinal gonderen : {kimden}\nOrijinal tarih    : {coz(org,'Date')}\n"
                      + "-"*50 + f"\n\n{gvd.strip() or '(metin govdesi yok)'}\n")
        S.send_message(y, from_addr=KUL)
        M.store(i, "+FLAGS", "\\Seen")
        print(f"  aktarildi: {kimden[:34]} | {konu[:38]}")
M.logout()
print("bitti")
