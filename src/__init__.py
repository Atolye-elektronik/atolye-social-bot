"""Atölye Elektronik sosyal medya otomasyonu.

Modüller `python -m src.<modul>` ile çalıştırılıyor; paket her seferinde
burada import edildiği için konsol kodlaması da burada ayarlanıyor.
"""

import sys


def _konsolu_utf8_yap() -> None:
    """Çıktı akışlarını utf-8'e çevirir.

    Windows konsolu cp1254 ile açılıyor ve çıktılardaki emoji/Türkçe
    karakterler UnicodeEncodeError'la üretimi ortasında kesiyordu. Her komuta
    elle PYTHONIOENCODING=utf-8 vermek yerine akışları burada çeviriyoruz;
    CI (Linux) zaten utf-8 olduğu için orada bir şey değişmiyor.
    """
    for akis in (sys.stdout, sys.stderr):
        try:
            akis.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError, OSError):
            # Akış TextIOWrapper değilse (test içinde StringIO, kapatılmış
            # akış) kodlamaya dokunmuyoruz — kırmaktansa olduğu gibi bırak.
            pass


_konsolu_utf8_yap()
