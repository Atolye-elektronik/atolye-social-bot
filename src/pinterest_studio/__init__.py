"""Pinterest arayüz otomasyonu — App ID istemeden pin atar.

Resmî API (src/pinterest.py) bir işletme hesabı ve onaylı developer app
istiyor; onay gelene kadar attığın pin'ler herkese açık görünmüyor. Bu modül
gerçek tarayıcıyı sürerek pin'i normal arayüzden atar: kişisel hesapla
çalışır, inceleme beklemez, pin ilk günden herkese açık olur. Karşılığında
tarayıcı otomasyonunun kırılganlığını kabul ederiz.

    python -m src.pinterest_studio saglik            # oturum ayakta mı
    python -m src.pinterest_studio dene --only SLUG  # tek postu arayüzden at
"""

from .session import OturumDustu, StudioError
from .upload import publish, studio_paylas

__all__ = ["OturumDustu", "StudioError", "publish", "studio_paylas"]
