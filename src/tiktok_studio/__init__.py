"""TikTok Studio otomasyonu — yükleme, zamanlama, analitik ve yorumlar.

Resmî Content Posting API (src/tiktok.py) yerine gerçek Studio arayüzünü
kullanır; böylece doğrudan yayınlama ve TikTok'un kendi zamanlayıcısı
kullanılabilir. Karşılığında tarayıcı otomasyonunun kırılganlığını kabul
ederiz — bu yüzden her yol, hata durumunda API taslak moduna düşer.

    python -m src.tiktok_studio saglik      # oturum ayakta mı
    python -m src.tiktok_studio zamanla     # yaklaşan postları TikTok'a planla
    python -m src.tiktok_studio analitik    # analitiği state/ altına yaz
    python -m src.tiktok_studio yorumlar    # yorumları topla, taslak üret
"""

from .session import OturumDustu, StudioError
from .upload import publish, studio_paylas

__all__ = ["OturumDustu", "StudioError", "publish", "studio_paylas"]
