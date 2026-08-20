# Yedekleme ve Acil Kurtarma Planı

Güncelleme: 20.08.2026

## Yedek katmanları (hepsi ücretsiz, hepsi otomatik)

| Katman | Nerede | Güncellenme |
|---|---|---|
| Asıl | github.com/Atolye-elektronik/atolye-social-bot | anlık |
| Ayna | gitlab.com/atolye-elektronik-group/atolye-social-bot | her gece 04:00 (gitlab-yedek.yml) |
| Yerel | C:\Users\serdar\Desktop\atolye-temiz | her Pazar 12:00 (yerel-yedek-cek görevi) |

Depoda olmayanlar ve yerleri:
- Müzikler: atolye-temiz\content\muzik (kaynak: YouTube Ses Kitaplığı, yeniden indirilebilir)
- TikTok çerezi: yerel .tiktok_studio_state.json + GitHub'da şifreli ci/tiktok-cerez.enc
- Pinterest çerezi: yerel .pinterest_studio_state.json + GitHub secret PINTEREST_STUDIO_COOKIES
- API jetonları: GitHub Secrets + GitLab CI/CD Variables (çift kayıt); kaybolursa
  Meta/Google/Trendyol/HB panellerinden yeniden üretilir

## GitHub askıya alınırsa — GitLab'a dönüş (10 dk)

1. GitLab'da 6 zamanlamayı geri aç (Settings > CI/CD > Pipeline schedules
   veya API): 4391688 (HB sync), 4391689 (TY sync), 4391690 (publish),
   4395672 (tiktok), 4396177 (hikaye), 4396192 (pinterest).
2. CI dakikası: ay başındaysa kota hazır; değilse ~10$ dakika satın al
   (Grup > Usage quotas > Buy additional compute minutes).
3. Yerel klonun origin'i zaten GitLab — `git push origin main` ile son
   durumu it (ayna zaten güncelse gerekmez).
4. state/published.json GitLab'a aynalandığı için mükerrer paylaşım olmaz.

## GitLab da giderse — yerelden çalıştırma

Yerel klon + çerezler + .env (SMTP) buradadır. Jetonları panellerden
yeniden üret, yerelde `python -m src.main` elle koşar; kalıcı çözüm için
yeni bir git platformuna (Bitbucket/Codeberg) aynı workflow'lar taşınır.
