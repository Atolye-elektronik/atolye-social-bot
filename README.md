# Atölye Elektronik — Sosyal Medya Botu

Instagram, Facebook Page, Threads ve TikTok'a zamanlanmış paylaşım yapan bir bot.
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

Üçüncü bir akış da ürünlerden **carousel** (kaydırmalı albüm) taslakları
üretir: ürünün fotoğraflarından marka stilinde kapak + ürün + kapanış
slide'ları oluşturur, Instagram'da carousel, Facebook'ta çoklu fotoğraf
gönderisi olarak paylaşılır. Elle çalıştırmak için:

```bash
python -m src.carousel_source --count 2
# ya da tek bir ürün için:
python -m src.carousel_source --handle temel-elektronik-deney-seti
```

Carousel'lerin iki tipi var:

- **Klasik** (`carousel_source`) — kapak + ürün fotoğrafları + kapanış.
- **Senaryolu** (`senaryo_source`) — izleyiciyi hikayeye çeken kurgu:
  tanıdık bir dert → hayal → çözüm olarak ürün → sipariş çağrısı.
  Senaryo metni ürünün kategorisine göre otomatik seçilir (robot kitleri,
  başlangıç setleri, el aletleri, sensör/modüller, meslek lisesi setleri).

```bash
python -m src.senaryo_source --count 2
python -m src.senaryo_source --handle arduino-baslangic-seti
```

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
| `THREADS_ACCESS_TOKEN` | Threads token (Meta panelindeki User Token Generator) |
| `THREADS_USER_ID` | Threads hesap ID |
| `TIKTOK_CLIENT_KEY` | TikTok Client Key |
| `TIKTOK_CLIENT_SECRET` | TikTok Client Secret |
| `TIKTOK_REFRESH_TOKEN` | `tools/tiktok_auth.py` ile üretilir |
| `SHOPIFY_STORE` | Mağaza adı (`.myshopify.com` olmadan) |
| `SHOPIFY_ADMIN_TOKEN` | Shopify Admin API token'ı |
| `TRENDYOL_SUPPLIER_ID` | Trendyol satıcı ID |
| `TRENDYOL_API_KEY` | Trendyol API key |
| `TRENDYOL_API_SECRET` | Trendyol API secret |
| `HEPSIBURADA_MERCHANT_ID` | Hepsiburada Merchant ID (GUID, Basic auth kullanıcı adı) |
| `HEPSIBURADA_SECRET_KEY` | Hepsiburada secret key (Basic auth şifresi) |
| `HEPSIBURADA_DEV_USERNAME` | Geliştirici kullanıcı adı (User-Agent header'ı) |

Hepsiburada bilgileri destek kaydı yanıtıyla iletilir (test ortamı bilgileri
1-187090166767583 numaralı kayıtla geldi). Test ortamında çalışmak için
repo → Settings → Variables kısmına `HEPSIBURADA_ENV=sit` değişkenini ekle;
canlı ortam bilgileri gelince bu değişkeni silmen (veya `prod` yapman) yeterli.

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

## Threads hakkında

Threads, Instagram ile aynı şirkette olmasına rağmen ayrı bir API kullanıyor:
adres `graph.threads.net`, token da Meta token'ından farklı. Bu yüzden bir
kerelik ayrı bir yetkilendirme gerekiyor.

Meta App Dashboard → uygulama → **Add use cases** → *Access the Threads API*.
Sonra **Settings** sekmesinin altındaki **User Token Generator** bölümünden
Threads hesabını "Threads Tester" olarak ekle, davet Threads hesabında
(Ayarlar → İnternet sitesi izinleri → Davetler) kabul edilsin ve
**Generate Access Token** ile 60 gün geçerli token'ı al. Token'ı
`THREADS_ACCESS_TOKEN`, hesap ID'sini `THREADS_USER_ID` olarak kaydet.

Alternatif olarak OAuth akışı için `tools/threads_auth.py` kullanılabilir
(`THREADS_APP_ID` + `THREADS_APP_SECRET` ister).

Bir postu Threads'e göndermek için `platforms` satırına `threads` yazman
yeterli — bot metin, tek görsel, video ve carousel (2-20 görsel) paylaşımını
destekliyor. Threads metin sınırı 500 karakter; uzun metinler kelime sonunda
kesilir.

### Token yenileme

Threads token'ı **60 gün** geçerli. `threads-token` işi ayda bir çalışıp
token'ı süresi dolmadan yeniler ve yeni değeri CI değişkenine kendisi yazar.
Durumu istediğin an kontrol edebilirsin:

```bash
python -m src.threads_token --check
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

## Dosya düzeni

```
.github/workflows/publish.yml          Saatlik paylaşım akışı
.github/workflows/shopify-drafts.yml   Haftalık taslak üretimi
.github/workflows/carousel-drafts.yml  Haftalık carousel taslak üretimi
.github/workflows/trendyol-sync.yml    Trendyol sipariş takibi (saatlik)
.github/workflows/hepsiburada-sync.yml Hepsiburada sipariş takibi (saatlik)
src/marketplaces/trendyol_client.py    Trendyol API istemcisi
src/marketplaces/hepsiburada_client.py Hepsiburada API istemcisi
src/marketplaces/hepsiburada_sync.py   Hepsiburada sipariş senkronu
posts/                                 Paylaşımlar (markdown)
posts/media/                           Görseller ve videolar
posts/media/carousel/                  Üretilen carousel slide'ları
src/main.py                            Ana akış
src/instagram.py                       Instagram Graph API
src/facebook.py                        Facebook Page API
src/threads.py                         Threads API
src/threads_token.py                   Threads token yenileme
src/tiktok.py                          TikTok Content Posting API
src/shopify_source.py                  Shopify'dan taslak üretimi
src/carousel_source.py                 Ürünlerden klasik carousel üretimi
src/senaryo_source.py                  Senaryolu (hikayeli) carousel üretimi
src/carousel_gorsel.py                 Marka stilinde slide çizimi
src/posts.py                           Post dosyalarını okur
src/state.py                           Paylaşım kaydı
tools/tiktok_auth.py                   TikTok bir kerelik yetkilendirme
tools/threads_auth.py                  Threads OAuth yetkilendirmesi
state/published.json                   Bot tarafından yönetilir
state/carousel_seen.json               Carousel üretilen ürünler
```
