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

**platforms** — Nerelere paylaşılacak. Seçenekler: `instagram`, `facebook`, `tiktok`.
Birden fazlasını yazabilirsin. Boş bırakırsan Instagram ve Facebook varsayılır.

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
(carousel'de video desteklenmiyor). Carousel yalnızca Instagram ve
Facebook'ta çalışır; TikTok/YouTube bu postları atlar.

**publish_at** — Ne zaman paylaşılacağı, Türkiye saatiyle. Biçim `2026-08-01 10:00`.
Bu satırı silersen post ilk çalışmada hemen paylaşılır.

## Nasıl çalışır

Paylaşım akışı her saat başı çalışır, zamanı gelmiş ve daha önce
paylaşılmamış postları bulur, ilgili platformlara gönderir. Neyin
paylaşıldığı `state/published.json` dosyasında tutulur — o dosyayı elle
düzenlemene gerek yok, bot kendisi günceller.

## Video paylaşımı

Instagram videoları Reels olarak paylaşır. TikTok yalnızca video kabul eder.
Video dosyalarını da `posts/media/` klasörüne koy, `.mp4` uzantılı olsun.

GitHub'da tek dosya sınırı 100 MB. Daha büyük videolar için dosyayı Shopify'a
yükleyip `media` alanına CDN adresini yazmak daha iyi olur.
