# Atölye Elektronik — Sosyal Medya Botu

Instagram, Facebook Page ve TikTok'a zamanlanmış paylaşım yapan bir GitHub Actions botu.
Sunucu kiralamana gerek yok, her şey GitHub üzerinde ücretsiz çalışır.

## Nasıl çalışır

Paylaşmak istediğin her içerik `posts/` klasöründe bir markdown dosyası olur.
Dosyanın başında hangi platformlara ve ne zaman gideceği yazar, altında da
paylaşım metni bulunur. Bot her saat başı çalışır, zamanı gelmiş postları
bulur ve paylaşır. Aynı postu iki kez paylaşmaması için neyi ne zaman
paylaştığını `state/published.json` dosyasında tutar.

Görseller repo içinde durur ve GitHub'ın herkese açık dosya adresleri
üzerinden yayınlanır — Instagram'ın API'si görselin internetten erişilebilir
olmasını şart koştuğu için bu iş görür. İstersen Shopify CDN adreslerini de
kullanabilirsin.

Ayrıca haftalık çalışan ikinci bir akış, Shopify mağazandaki ürünlerden
otomatik post taslakları üretip pull request olarak açar. Metinleri gözden
geçirip birleştirdiğinde paylaşım sırasına girerler.

Üçüncü bir akış da her sabah terk edilmiş sepetlere bakar ve toplu alım
yapmaya çalışıp vazgeçenleri sana e-postayla bildirir. Ayrıntısı aşağıda.

## Kurulum

### 1. Repo'yu hazırla

Bu klasördeki dosyaları GitHub'da yeni bir **public** repo'ya yükle.
Public olması önemli — Instagram görselleri ancak herkese açık adreslerden
çekebiliyor. Token'lar repo'da değil, GitHub Secrets'ta saklandığı için
bu bir güvenlik sorunu yaratmaz.

### 2. Secrets'ı ekle

Repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Ad | Değer |
|---|---|
| `META_ACCESS_TOKEN` | Meta System User token'ın |
| `FB_PAGE_ID` | Facebook Page ID'n |
| `IG_USER_ID` | Instagram Business hesap ID'n |
| `TIKTOK_CLIENT_KEY` | TikTok Client Key |
| `TIKTOK_CLIENT_SECRET` | TikTok Client Secret |
| `TIKTOK_REFRESH_TOKEN` | `tools/tiktok_auth.py` ile üretilir |
| `SHOPIFY_STORE` | Mağaza adı (`.myshopify.com` olmadan) |
| `SHOPIFY_ADMIN_TOKEN` | Shopify Admin API token'ı |
| `SMTP_USER` | Bildirim gönderecek Gmail adresin |
| `SMTP_PASSWORD` | O hesabın **uygulama şifresi** (normal parolan değil) |
| `ALERT_EMAIL` | Bildirimlerin düşeceği adres (boşsa `SMTP_USER` kullanılır) |

`SMTP_HOST` ve `SMTP_PORT` istersen ayrıca verilebilir; verilmezse Gmail
(`smtp.gmail.com`, `587`) varsayılır.

TikTok ve Shopify değerlerini şimdilik boş bırakabilirsin; o platformlar
sadece atlanır, Instagram ve Facebook çalışmaya devam eder.

### 3. Actions'ı aç

Repo'nun **Actions** sekmesine git, çalıştırma iznini onayla.

### 4. Denemeden önce kuru çalıştır

Actions → **Sosyal medya paylaşımı** → **Run workflow** → *Sadece dene* kutusunu
işaretle → çalıştır. Hiçbir şey paylaşılmaz, sadece ne olacağını gösterir.
Çıktı beklediğin gibiyse kutuyu işaretlemeden tekrar çalıştır.

## Yeni post ekleme

`posts/` klasörüne yeni bir `.md` dosyası ekle. Biçimi `posts/README.md`
dosyasında anlatılıyor. Görseli de `posts/media/` klasörüne koy. Commit
ettiğinde iş biter — bot zamanı gelince paylaşır.

## Yerelde deneme

```bash
pip install -r requirements.txt

export META_ACCESS_TOKEN=...
export FB_PAGE_ID=...
export IG_USER_ID=...
export MEDIA_BASE_URL=https://raw.githubusercontent.com/KULLANICI/REPO/main

python -m src.main --dry-run
```

## TikTok hakkında

TikTok'un Content Posting API'si, uygulaman TikTok denetiminden geçene kadar
paylaşımları **sadece sen görebilirsin** (SELF_ONLY) modunda yayınlar.
Denetime başvurmak için TikTok, entegrasyonun uçtan uca çalıştığını gösteren
bir demo video istiyor. Yani sıralama şöyle: önce bu botu TikTok'a bağla ve
bir test videosu paylaş, o akışın ekran kaydını al, sonra TikTok Developers
panelinden Production başvurusunu gönder.

Bir kerelik yetkilendirme için:

```bash
export TIKTOK_CLIENT_KEY=...
export TIKTOK_CLIENT_SECRET=...
python tools/tiktok_auth.py
```

## Terk edilmiş sepet takibi

Shopify'ın kendi "terk edilmiş ödeme" e-postası müşteriye otomatik gider ve
onu mutlaka açmalısın (Ayarlar → Bildirimler). Ama jenerik bir hatırlatma,
sınıfına 20 defter almaya çalışıp vazgeçen bir öğretmeni geri getirmez —
onun ihtiyacı proforma fatura, havale bilgisi ya da telefonla teyittir.

`sepet-takip.yml` her sabah 10:00'da (TR) son 14 günün terk edilmiş
sepetlerine bakar, daha önce bildirmediklerini ayıklar ve sana tek bir
e-posta atar. Bir sepette **10 adetten fazla** ürün varsa ya da tutar
**1.500 ₺'yi** geçiyorsa "toplu alım" sayılıp listenin başına konur ve
yanına kopyalayıp gönderebileceğin hazır bir mesaj eklenir.

Müşteri adı, e-postası ve telefonu **yalnızca sana giden e-postada** yer alır.
Repoya, `state/` dosyalarına ve Actions loglarına yazılmaz — repo herkese
açık olduğu için bu ayrım önemli. State dosyası sadece sepet kimliklerini
tutar, o da aynı sepeti iki kez bildirmemek için.

Elle çalıştırmak için: Actions → **Terk edilmiş sepet takibi** → *Run workflow*.
İlk denemede *Sadece dene* kutusunu işaretle; e-posta gitmez, sadece kaç sepet
bulduğunu yazar.

```bash
export SHOPIFY_STORE=... SHOPIFY_ADMIN_TOKEN=...
python -m src.sepet_takip --dry-run
```

## Okullara tanıtım e-postası

Meslek liselerinin bölüm şefleri malzeme listesini eylülün ilk iki haftasında
kesinleştiriyor. Okul okul dolaşmaya vakit yoksa en hızlı yol, okulun kendi
sitesinde zaten yayınlanmış kurumsal adrese tek sayfalık fiyat listesini
göndermek.

`src/okul_daveti.py` bunu yapar. Her e-posta okul ve bölüm adıyla
kişiselleştirilir, `pazarlama/atolye-elektronik-okul-fiyat-listesi.pdf` ek
olarak gider, altına listeden çıkma satırı konur ve gönderimler arasında
varsayılan 8 saniye beklenir.

Liste dosyasını `pazarlama/okullar.csv` olarak hazırla — sütunlar
`okul,bolum,eposta`, örneği `pazarlama/okullar.ornek.csv` içinde. Bu dosya
`.gitignore`'da; repoya girmez. Gönderim kaydı da adres değil, adresin
özetini tutar.

```bash
export SMTP_USER=... SMTP_PASSWORD=...   # Gmail uygulama şifresi
export IMZA_ADI="Adın Soyadın"

python -m src.okul_daveti --liste pazarlama/okullar.csv --dry-run
python -m src.okul_daveti --liste pazarlama/okullar.csv --limit 50
```

İlk gün 50 okulla başla, gelen dönüşe göre devam et. Gmail'in günlük gönderim
sınırı var; tek seferde yüzlerce adrese gitmek hem sınıra takılır hem de
spam'e düşme riskini artırır.

Fiyat listesini güncellemek için `pazarlama/fiyat-listesi.html` dosyasını
düzenleyip PDF'i yeniden üret:

```bash
chromium --headless --no-pdf-header-footer \
  --print-to-pdf=pazarlama/atolye-elektronik-okul-fiyat-listesi.pdf \
  pazarlama/fiyat-listesi.html
```

## Dosya düzeni

```
.github/workflows/publish.yml         Saatlik paylaşım akışı
.github/workflows/shopify-drafts.yml  Haftalık taslak üretimi
.github/workflows/sepet-takip.yml     Günlük terk edilmiş sepet bildirimi
posts/                                Paylaşımlar (markdown)
posts/media/                          Görseller ve videolar
src/main.py                           Ana akış
src/instagram.py                      Instagram Graph API
src/facebook.py                       Facebook Page API
src/tiktok.py                         TikTok Content Posting API
src/shopify_source.py                 Shopify'dan taslak üretimi
src/sepet_takip.py                    Terk edilmiş sepet bildirimi
src/okul_daveti.py                    Okullara tanıtım e-postası
pazarlama/fiyat-listesi.html          Fiyat listesinin kaynağı
pazarlama/okullar.ornek.csv           Okul listesi örneği
src/posts.py                          Post dosyalarını okur
src/state.py                          Paylaşım kaydı
tools/tiktok_auth.py                  TikTok bir kerelik yetkilendirme
state/published.json                  Bot tarafından yönetilir
state/sepet_bildirilen.json           Bot tarafından yönetilir
```
