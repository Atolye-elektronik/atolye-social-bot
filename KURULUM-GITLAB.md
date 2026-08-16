# GitLab kurulumu (adım adım)

GitHub hesabı askıya alındığı için bot GitLab'da da çalışacak şekilde hazırlandı.
Kodun tamamı aynı; sadece zamanlanmış işler `.gitlab-ci.yml` dosyasından yürüyor
ve bekleyen siparişler GitHub issue yerine GitLab issue olarak açılıyor.

Aşağıdaki adımlar toplam 10-15 dakika sürer. Sırayla git.

## 1. GitLab hesabı ve proje

1. https://gitlab.com/users/sign_up adresinden ücretsiz hesap aç
   (aynı e-posta ile: atolyeelektronik07@gmail.com).
2. Sağ üstteki **+** → **New project/repository** → **Create blank project**
   - Project name: `atolye-social-bot`
   - Visibility: **Private** (GitHub'dakinin aksine burada public olması gerekmiyor;
     görseller için aşağıdaki nota bak)
   - "Initialize repository with a README" kutusunu **işaretleme**
3. **Create project**.

> **Görseller hakkında:** Instagram, paylaşılacak görselin internetten
> erişilebilir olmasını şart koşuyor. GitHub'da repo public olduğu için
> `raw.githubusercontent.com` adresleri işe yarıyordu. GitLab'da proje private
> kalacaksa `MEDIA_BASE_URL` değişkenini Shopify CDN adresine çevir
> (Shopify'a yüklediğin görsellerin adresi), ya da projeyi public yap.
>
> **Carousel kullanacaksan proje public olmalı.** Carousel slide'ları bot
> tarafından üretilip repoya yazılıyor (`posts/media/carousel/`), yani
> Shopify CDN'de bulunmuyorlar — `MEDIA_BASE_URL`'i Shopify'a çevirmek bu
> görselleri kurtarmaz, carousel paylaşımları hata verir. Proje public
> olduğunda bot GitLab raw adreslerini kendisi kuruyor, ek ayar gerekmiyor.
> Projeyi private tutmak zorundaysan slide'ları bir CDN'e yükleyip
> `MEDIA_BASE_URL`'i oraya çevirmen gerekir.

## 2. Kodu GitLab'a yükle

Projeyi oluşturduktan sonra GitLab sana komutları gösterir. Bilgisayarında
repo'nun bir kopyası varsa:

```bash
git remote add gitlab https://gitlab.com/KULLANICI_ADIN/atolye-social-bot.git
git push -u gitlab main
```

Yoksa bu oturumdaki yedeği kullanabilirsin (`hepsiburada-entegrasyon.patch`
dosyası sana gönderilmişti) — bana söyle, adımları çıkarayım.

## 3. Değişkenleri (secrets) ekle

**Settings → CI/CD → Variables → Add variable**

Her biri için: *Type: Variable*, **Masked** işaretli, **Protected** işaretsiz.

| Key | Değer |
|---|---|
| `GITLAB_TOKEN` | 4. adımda üreteceğin token |
| `HEPSIBURADA_MERCHANT_ID` | `2c99312b-0dfd-4d3d-9573-df8177140f47` |
| `HEPSIBURADA_SECRET_KEY` | Hepsiburada secret key |
| `HEPSIBURADA_DEV_USERNAME` | `atolyeelektronik_dev` |
| `HEPSIBURADA_ENV` | `sit` (canlı bilgiler gelince sil) |
| `TRENDYOL_SUPPLIER_ID` | Trendyol satıcı ID |
| `TRENDYOL_API_KEY` | Trendyol API key |
| `TRENDYOL_API_SECRET` | Trendyol API secret |
| `META_ACCESS_TOKEN` | Meta System User token |
| `FB_PAGE_ID` | Facebook Page ID |
| `IG_USER_ID` | Instagram Business hesap ID |
| `THREADS_ACCESS_TOKEN` | Threads token (`tools/threads_auth.py` üretir) |
| `THREADS_USER_ID` | Threads hesap ID (aynı script verir) |
| `SHOPIFY_STORE` | Mağaza adı (`.myshopify.com` olmadan) |
| `SHOPIFY_ADMIN_TOKEN` | Shopify Admin API token |
| `MEDIA_BASE_URL` | Görsellerin bulunduğu adres |

TikTok/YouTube kullanacaksan onların değişkenlerini de ekle; eklemezsen o
platformlar sessizce atlanır.

## 4. GITLAB_TOKEN üret

Bot, sipariş durumunu repoya geri yazdığı ve issue açtığı için yazma yetkisi
olan bir token'a ihtiyaç duyuyor.

**Settings → Access tokens → Add new token**
- Token name: `bot`
- Role: **Maintainer**
- Scopes: **api** ve **write_repository** (ikisini de işaretle)
- **Create project access token** → çıkan değeri kopyala ve 3. adımdaki
  `GITLAB_TOKEN` değişkenine yapıştır. (Bu değer bir daha gösterilmez.)

## 5. Zamanlamaları kur

**Build → Pipeline schedules → New schedule**

Aşağıdaki on bir zamanlamayı ekle. Her birinde *Interval Pattern* kutusuna
"Custom" seçip cron ifadesini yaz, *Variables* kısmına da `JOB` anahtarını
ve değerini gir. Timezone: **Istanbul**.

| Açıklama | Cron | Değişken |
|---|---|---|
| Sosyal medya paylaşımı | `5 * * * *` | `JOB` = `publish` |
| Trendyol sipariş senkronu | `13 * * * *` | `JOB` = `trendyol-sync` |
| Hepsiburada sipariş senkronu | `27 * * * *` | `JOB` = `hepsiburada-sync` |
| Shopify taslakları (pazartesi) | `0 6 * * 1` | `JOB` = `shopify-drafts` |
| Carousel taslakları (perşembe) | `0 6 * * 4` | `JOB` = `carousel-drafts` |
| İçerik takvimi (pazar) | `0 6 * * 0` | `JOB` = `takvim` |
| Threads token yenileme (ayda bir) | `0 4 1 * *` | `JOB` = `threads-token` |
| TikTok Studio sağlık kontrolü | `0 6 * * *` | `JOB` = `tiktok-saglik` |
| TikTok zamanlama | `20 6 * * *` | `JOB` = `tiktok-zamanla` |
| TikTok analitiği | `0 8 * * *` | `JOB` = `tiktok-analitik` |
| TikTok yorumları (pazartesi) | `30 8 * * 1` | `JOB` = `tiktok-yorumlar` |

Threads token'ı 60 gün geçerli. Aylık iş onu süresi dolmadan yeniler ve yeni
değeri `THREADS_ACCESS_TOKEN` değişkenine kendisi yazar — bunun için
`GITLAB_TOKEN`'ın **api** yetkisi olması yeterli (4. adımda zaten veriliyor).
Bu zamanlamayı kurmazsan 60 gün sonra Threads paylaşımları durur ve
`tools/threads_auth.py` ile elle yeniden yetkilendirmen gerekir.

Carousel işine isteğe bağlı üç değişken daha verebilirsin: `TIP` (`klasik`,
`senaryo` ya da boş bırakırsan ikisinden birer tane), `URUN` (yalnızca o
Shopify handle'ı için üret) ve `COUNT` (kaç tane üretilsin).

Dört TikTok işi, diğerlerinden farklı olarak gerçek bir tarayıcı çalıştırıyor
ve `TIKTOK_STUDIO_COOKIES` değişkenine ihtiyaç duyuyor. Bu değişkeni
`python tools/tiktok_studio_login.py` üretir; kurulumu ve oturum düştüğünde ne
yapılacağı [KURULUM-TIKTOK-STUDIO.md](KURULUM-TIKTOK-STUDIO.md) dosyasında.
Değişkeni eklemezsen bu dört iş hata verir, geri kalan akışlar etkilenmez.

Elle video üretmek için `JOB=tiktok-video` ve `POST=<post dosya adı>`
değişkenleriyle bir pipeline çalıştır — üretilen mp4 merge request olarak gelir.

## 6. İlk denemeyi yap

**Build → Pipeline schedules** listesinde "Hepsiburada sipariş senkronu"
satırının sağındaki ▶ (Run pipeline) düğmesine bas.

Beklenen sonuç: iş yeşile döner, **Plan → Issues** altında
*"Hepsiburada: Kargoya verilmesi gereken siparişler"* başlıklı bir issue
oluşur (bekleyen sipariş varsa listeler, yoksa "sipariş yok ✅" yazar).

Bir hata çıkarsa iş kaydındaki (job log) çıktıyı bana ilet, düzeltirim.

## Elle çalıştırma

**Build → Pipelines → Run pipeline** → değişken olarak `JOB` = ilgili iş adı →
Run. Paylaşım işine ek argüman geçmek için `EXTRA_ARGS` = `--dry-run` gibi bir
değişken de ekleyebilirsin.

## Shopify ürünlerini Hepsiburada'ya açma

`hepsiburada-urun-ekle` işi bilerek zamanlanmıyor — Hepsiburada'da gerçek ürün
açtığı için sadece elle çalıştırılır. Üç adımda ilerle:

**1. Kategori ID'lerini bul.** Run pipeline → `JOB` = `hepsiburada-urun-ekle`,
`KATEGORI_ARA` = `robot`. İş kaydında kategori adları ve ID'leri listelenir.
Aynısını `defter` için tekrarla.

**2. Eşlemeyi doldur.** Bulduğun ID'leri `content/hepsiburada_kategori.json`
dosyasındaki `categoryId` alanlarına yaz ve commit'le. Bu alanlar `null`
kaldığı sürece hiçbir ürün gönderilmez. Kategorinin zorunlu alanları varsa
(renk, materyal gibi) `sabit_ozellikler` bloğuna eklemen gerekir.

**3. Önce kuru çalıştır, sonra gönder.** `JOB` = `hepsiburada-urun-ekle` ile
çalıştır — hiçbir şey gönderilmez, gönderilecek payload `payload.json`
artifact'ı olarak iner. İçeriği doğruysa aynı işi bir de `GONDER` = `1`
değişkeniyle çalıştır.

| Değişken | İşe yarar |
|---|---|
| `KATEGORI_ARA` | Sadece kategori arar, ürün göndermez |
| `GONDER` = `1` | Gerçekten gönderir (yoksa kuru çalıştırma) |
| `COUNT` | Son kaç Shopify ürünü (varsayılan 7) |
| `BARKOD_URET` = `0` | Barkod üretimini kapatır (varsayılan açık) |

Gönderilen SKU'lar `state/hepsiburada_urunler.json` dosyasına yazılıp repoya
commit'lenir, ikinci çalıştırmada tekrar gönderilmezler.

> **Ortam uyarısı:** Yukarıdaki değişken listesinde `HEPSIBURADA_ENV` = `sit`
> yazıyor. Bu değişken duruyorken ürünler **test ortamına** açılır, canlı
> mağazada görünmez. Canlıya göndermek için değişkeni sil (ya da `prod` yap)
> — ama önce canlı ortam secret key'inin geldiğinden emin ol.

## GitHub geri gelirse

Hiçbir şey silmene gerek yok. `.github/workflows/` dosyaları duruyor; iki
platform da aynı kodu çalıştırabiliyor. Aynı anda ikisini birden açık
bırakırsan aynı işler iki kez çalışır — o yüzden birinde zamanlamaları
kapatman yeterli.
