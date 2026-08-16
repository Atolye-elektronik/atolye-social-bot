# Atölye Elektronik — Sosyal Medya Botu

Instagram, Facebook Page, Threads ve TikTok'a zamanlanmış paylaşım yapan bir GitHub Actions botu.
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

## Shopify ürünlerini Hepsiburada'ya açma

Hepsiburada'da ürün açmak iki ayrı adım — katalog ve listeleme:

1. **Katalog:** ürün bilgisi MPOP'a gönderilir, Hepsiburada onaylar ve ürüne
   bir `hepsiburadaSku` verir. Bunu `hepsiburada_urun_ekle.py` yapar.
   Fiyat ve stok da bu gönderimin içinde gidiyor (kategori şemasında
   `price` / `stock` alanları var), yani ayrı bir listeleme adımı şart değil.
2. **Güncelleme:** ürünler açıldıktan sonra fiyat/stok değişikliklerini
   `hepsiburada_update_price_stock.py` listing API'si üzerinden yazar.

Kategori eşlemesi `content/hepsiburada_kategori.json` dosyasında hazır:
robot kitleri **Bilim Seti** (23024292), defterler **Ciltli Defterler**
(15064) kategorisine açılıyor. Bu kategorilerin zorunlu ek alanları
(`yas_araligi`, Paket Görseli) dolduruldu.

Önce kategori eşlemesini doldur — `content/hepsiburada_kategori.json` içindeki
`categoryId` alanları boşken hiçbir ürün gönderilmez:

```bash
cd src/marketplaces
python hepsiburada_urun_ekle.py --kategori-ara "robot"
python -c "import hepsiburada_catalog as k; print(k.zorunlu_ozellikler(<categoryId>))"
```

Sonra kuru çalıştır, çıktıyı gözden geçir, ancak ondan sonra gönder:

```bash
python hepsiburada_urun_ekle.py --count 7 --cikti payload.json
python hepsiburada_urun_ekle.py --count 7 --gonder
```

`--gonder` verilmedikçe hiçbir şey gönderilmez. Gönderilen SKU'lar
`state/hepsiburada_urunler.json` dosyasına yazılır, ikinci çalıştırmada
tekrar gönderilmezler (`--tekrar` bunu geçersiz kılar).

**Ürün adı:** Hepsiburada 100 karakter sınırı koyuyor. Varyantlı üründe
başlıktaki seçenek listesi ayıklanır (`Sınıf Paketi (10 / 20 / 30 Adet)` +
`10 Adet` → `Sınıf Paketi - 10 Adet`). Ad hâlâ uzunsa önce sondaki parantezli
açıklama atılır, son çare kelime sınırından kesilir. Sonucu beğenmezsen o
kategorinin `ad_override` bloğuna `"SKU": "istediğin ad"` yazabilirsin.

**Barkod:** Hepsiburada yeni ürün için EAN-13 barkod istiyor. Shopify'daki
varyantta barkod yoksa ürün atlanır; `--barkod-uret` verirsen SKU'dan sabit
bir EAN-13 üretilir. Üretilen barkodlar GS1'in mağaza içi kullanıma ayırdığı
200-299 önek aralığını kullanır, yani kimsenin tescilli barkoduyla çakışmaz.
Kalıcı çözüm GS1 Türkiye'den kendi firma önekini almaktır.

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
| `THREADS_ACCESS_TOKEN` | `tools/threads_auth.py` ile üretilir |
| `THREADS_USER_ID` | Aynı script verir |
| `GH_SECRETS_TOKEN` | Threads token'ını otomatik yenilemek için (aşağıya bak) |
| `TIKTOK_CLIENT_KEY` | TikTok Client Key |
| `TIKTOK_CLIENT_SECRET` | TikTok Client Secret |
| `TIKTOK_REFRESH_TOKEN` | `tools/tiktok_auth.py` ile üretilir |
| `TIKTOK_STUDIO_COOKIES` | `tools/tiktok_studio_login.py` ile üretilir (Studio otomasyonu için) |
| `SHOPIFY_STORE` | Mağaza adı (`.myshopify.com` olmadan) |
| `SHOPIFY_ADMIN_TOKEN` | Shopify Admin API token'ı |
| `TRENDYOL_SUPPLIER_ID` | Trendyol satıcı ID |
| `TRENDYOL_API_KEY` | Trendyol API key |
| `TRENDYOL_API_SECRET` | Trendyol API secret |
| `HEPSIBURADA_MERCHANT_ID` | Hepsiburada Merchant ID (GUID, Basic auth kullanıcı adı) |
| `HEPSIBURADA_SECRET_KEY` | Hepsiburada secret key (Basic auth şifresi) |
| `HEPSIBURADA_DEV_USERNAME` | Geliştirici kullanıcı adı (User-Agent header'ı) |
| `HEPSIBURADA_MPOP_USERNAME` | Ürün açma (MPOP) kullanıcı adı — boşsa `HEPSIBURADA_DEV_USERNAME` kullanılır |
| `HEPSIBURADA_MPOP_PASSWORD` | Ürün açma (MPOP) şifresi — boşsa `HEPSIBURADA_SECRET_KEY` kullanılır |

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

Önce Meta App Dashboard'da uygulamana **Threads API** ürününü ekle,
`threads_basic` ve `threads_content_publish` izinlerini seç, Redirect
Callback URI olarak `https://atolyeelektronik.com/threads/callback` tanımla.
Sonra kendi bilgisayarında:

```bash
export THREADS_APP_ID=...
export THREADS_APP_SECRET=...
python tools/threads_auth.py
```

Script sana `THREADS_ACCESS_TOKEN` ve `THREADS_USER_ID` verir; ikisini de
secret olarak ekle. Bir postu Threads'e göndermek için `platforms` satırına
`threads` yazman yeterli — bot metin, tek görsel, video ve carousel (2-20
görsel) paylaşımlarını destekliyor. Threads metin sınırı 500 karakter; uzun
metinler kelime sonunda kesilir.

### Token yenileme

Threads token'ı **60 gün** geçerli. `Threads token yenile` akışı ayın 1'inde
çalışıp token'ı süresi dolmadan yeniler, böylece elle bir şey yapman gerekmez.
Yenilenen token'ı secret'a yazabilmesi için secret yazma yetkisi olan bir
token gerekiyor:

Settings → Developer settings → **Fine-grained personal access token** →
sadece bu repo, izin olarak *Secrets: Read and write* → çıkan değeri
`GH_SECRETS_TOKEN` secret'ı olarak ekle.

Bu token'ı eklemezsen akış yine çalışır, sadece uyarı verir ve yeni değeri
kaydedemez — o durumda 60 günde bir `tools/threads_auth.py` çalıştırman gerekir.
Token'ın durumunu istediğin an kontrol edebilirsin:

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

## TikTok Studio otomasyonu

API'nin bu kısıtını aşmanın ikinci bir yolu var: **TikTok Studio** arayüzünü
otomatikleştirmek. Bu akış gerçek bir tarayıcı sürerek videoyu doğrudan
yayınlayabiliyor, ileri tarihe zamanlayabiliyor, analitiği çekebiliyor ve
yorumları toplayabiliyor.

Bir postu bu yoldan göndermek için `platforms` satırına `tiktok_studio` yaz
(`tiktok` ile ikisini birden yazma — video iki kez gider).

```bash
python -m src.tiktok_studio saglik           # oturum geçerli mi
python -m src.tiktok_studio zamanla --gun 7  # yaklaşan postları TikTok'a planla
python -m src.tiktok_studio analitik         # analitiği state/ altına yaz
python -m src.tiktok_studio yorumlar         # yorumları topla, yanıt taslağı üret
```

Bunun belgelenmiş bir API olmadığını unutma: TikTok oturum çerezleri birkaç
haftada bir düşer ve arayüz değişebilir. Bu yüzden akış üç şeyi garanti ediyor —
Studio başarısız olursa resmî API'nin taslak moduna düşer, her hatada ekran
görüntüsü bırakır, ve günlük sağlık kontrolü çerez düşmeden bir hafta önce uyarır.

En dayanıklı kullanım **zamanlama**: video paylaşım gününden önce yüklenip
TikTok'un kendi zamanlayıcısına bırakılır, böylece paylaşım anında ne CI'ın
çalışmasına ne oturumun geçerli olmasına gerek kalır.

Kurulum ve sorun giderme: **[KURULUM-TIKTOK-STUDIO.md](KURULUM-TIKTOK-STUDIO.md)**

### Görsellerden dikey video

Elinde video yoksa ürün fotoğraflarından üretebilirsin — carousel'lerle aynı
marka dilinde, 1080x1920, yavaş yakınlaşan kareler:

```bash
python -m src.video_uretim --post 2026-08-20-senaryo-arduino-baslangic-seti
```

## Dosya düzeni

```
.github/workflows/publish.yml          Saatlik paylaşım akışı
.github/workflows/tiktok-studio.yml    TikTok Studio (sağlık, zamanlama, analitik, yorum)
.github/workflows/tiktok-video.yml     Görsellerden dikey video üretimi (elle)
.github/workflows/threads-token.yml    Threads token yenileme (aylık)
.github/workflows/shopify-drafts.yml   Haftalık taslak üretimi
.github/workflows/carousel-drafts.yml  Haftalık carousel taslak üretimi
.github/workflows/trendyol-sync.yml    Trendyol sipariş takibi (saatlik)
.github/workflows/hepsiburada-sync.yml Hepsiburada sipariş takibi (saatlik)
src/marketplaces/trendyol_client.py    Trendyol API istemcisi
src/marketplaces/hepsiburada_client.py Hepsiburada API istemcisi (sipariş + fiyat/stok)
src/marketplaces/hepsiburada_catalog.py Hepsiburada MPOP istemcisi (kategori + ürün açma)
src/marketplaces/hepsiburada_sync.py   Hepsiburada sipariş senkronu
src/marketplaces/hepsiburada_urun_ekle.py Shopify ürünlerini Hepsiburada'ya açar
content/hepsiburada_kategori.json      Shopify product_type -> HB categoryId eşlemesi
posts/                                 Paylaşımlar (markdown)
posts/media/                           Görseller ve videolar
posts/media/carousel/                  Üretilen carousel slide'ları
src/main.py                            Ana akış
src/instagram.py                       Instagram Graph API
src/facebook.py                        Facebook Page API
src/threads.py                         Threads API
src/threads_token.py                   Threads token yenileme
src/tiktok.py                          TikTok Content Posting API
src/tiktok_studio/                     TikTok Studio otomasyonu (tarayıcı)
src/tiktok_studio/selectors.py         Arayüz seçicileri — bir şey bozulunca burayı düzelt
src/tiktok_studio/session.py           Oturum, hata dökümü, sağlık kontrolü
src/tiktok_studio/upload.py            Video yükleme ve zamanlama
src/tiktok_studio/analytics.py         Analitik çekme
src/tiktok_studio/comments.py          Yorum toplama ve yanıt taslağı
src/video_uretim.py                    Görsellerden dikey video (ffmpeg)
src/shopify_source.py                  Shopify'dan taslak üretimi
src/carousel_source.py                 Ürünlerden klasik carousel üretimi
src/senaryo_source.py                  Senaryolu (hikayeli) carousel üretimi
src/carousel_gorsel.py                 Marka stilinde slide çizimi
src/posts.py                           Post dosyalarını okur
src/state.py                           Paylaşım kaydı
tools/tiktok_auth.py                   TikTok bir kerelik yetkilendirme
tools/tiktok_studio_login.py           TikTok Studio oturum çerezi üretimi
content/yorum_yanitlari.json           TikTok yorumları için hazır yanıt kuralları
tools/threads_auth.py                  Threads bir kerelik yetkilendirme
state/published.json                   Bot tarafından yönetilir
state/carousel_seen.json               Carousel üretilen ürünler
```
