# Post klasörü

Her paylaşım bu klasörde bir `.md` dosyasıdır. Dosya adı postun kimliğidir,
bu yüzden bir kez paylaşıldıktan sonra adını değiştirme (yoksa tekrar paylaşılır).

## Dosya biçimi

```markdown
---
platforms: [instagram, facebook]
media: posts/media/urun1.jpg
publish_at: 2026-08-01 10:00
---
Buraya paylaşım metni gelir.

Birden fazla satır olabilir. #atolyeelektronik
```

## Alanlar

**platforms** — Nerelere paylaşılacak. Seçenekler: `instagram`, `facebook`,
`threads`, `tiktok`, `youtube`. Birden fazlasını yazabilirsin. Boş bırakırsan
Instagram ve Facebook varsayılır. Otomatik üretilen taslaklara Threads de
ekleniyor; bunu değiştirmek için `POST_PLATFORMS` değişkenini kullan
(örn. `POST_PLATFORMS=instagram,facebook`).

**media** — Paylaşılacak görsel veya video. İki şekilde verilebilir:
repo içindeki bir dosya yolu (`posts/media/urun1.jpg`) ya da doğrudan bir
internet adresi (`https://cdn.shopify.com/...`). Instagram medyasız paylaşım
kabul etmiyor; Facebook kabul ediyor, o yüzden sadece Facebook'a atacaksan
bu satırı silebilirsin.

Birden fazla görseli köşeli parantezle verirsen post **carousel** olur:

```markdown
media: [posts/media/slide1.jpg, posts/media/slide2.jpg, posts/media/slide3.jpg]
```

Instagram'da kaydırmalı albüm, Facebook'ta çoklu fotoğraf gönderisi olarak
paylaşılır. Instagram en fazla 10 görsel kabul eder, hepsi resim olmalı
(carousel'de video desteklenmiyor). Carousel Instagram, Facebook ve
Threads'te çalışır; TikTok/YouTube bu postları atlar. Threads 20 görsele
kadar izin verir.

## Threads'e özel alanlar

**threads_text** — Threads'e giden metni ayrı yazmak istersen. Threads
sınırı 500 karakter; bu satırı yazmazsan post metni kullanılır ve gerekirse
kelime sonunda kısaltılır.

**threads_reply_control** — Gönderiye kimler yanıt verebilir:
`everyone` (varsayılan), `accounts_you_follow`, `mentioned_only`.

Threads, Instagram'ın aksine görselsiz (sadece metin) paylaşıma da izin verir.

**publish_at** — Ne zaman paylaşılacağı, Türkiye saatiyle. Biçim `2026-08-01 10:00`.
Bu satırı silersen post ilk çalışmada hemen paylaşılır.

## Nasıl çalışır

Paylaşım akışı her saat başı çalışır, zamanı gelmiş ve daha önce
paylaşılmamış postları bulur, ilgili platformlara gönderir. Neyin
paylaşıldığı `state/published.json` dosyasında tutulur — o dosyayı elle
düzenlemene gerek yok, bot kendisi günceller.

**Tek turda en fazla bir post paylaşılır.** Bot bir süre çalışmazsa (tatil,
kapalı hesap, bozuk zamanlama) geride birikmiş postlar oluşur; sınır olmasaydı
bot ilk çalıştığında hepsini arka arkaya gönderir, akış spam'e döner ve Meta'nın
hız sınırına takılabilirdi. Sınır sayesinde kuyruk saat başı birer birer boşalır.
Değiştirmek için `MAX_PER_RUN` değişkenini kullan (`0` = sınırsız) ya da elle
çalıştırırken `--max 3` gibi bir değer ver. `--only` ile tek post gönderirken
sınır zaten uygulanmaz.

## Video paylaşımı

Instagram videoları Reels olarak paylaşır. TikTok yalnızca video kabul eder.
Video dosyalarını da `posts/media/` klasörüne koy, `.mp4` uzantılı olsun.

GitHub'da tek dosya sınırı 100 MB. Daha büyük videolar için dosyayı Shopify'a
yükleyip `media` alanına CDN adresini yazmak daha iyi olur.
