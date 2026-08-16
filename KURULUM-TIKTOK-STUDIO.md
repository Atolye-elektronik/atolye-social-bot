# TikTok Studio otomasyonu — kurulum

Bu akış, TikTok'un resmî API'sinin yapamadığı işleri **gerçek TikTok Studio
arayüzü** üzerinden yapar: doğrudan yayınlama, ileri tarihe zamanlama,
analitik okuma ve yorum toplama.

## Neden ayrı bir akış?

| | Resmî API (`src/tiktok.py`) | Studio (`src/tiktok_studio/`) |
|---|---|---|
| Doğrudan yayın | Uygulama denetimden geçmeden ❌ | ✅ |
| İleri tarihe zamanlama | ❌ | ✅ (en fazla 10 gün) |
| Analitik | ❌ | ✅ |
| Yorumlar | ❌ | ✅ (okuma) |
| Kırılganlık | Düşük — belgelenmiş API | Yüksek — arayüz değişebilir |

İkisi birbirinin yedeği: Studio başarısız olursa otomasyon resmî API'nin
taslak moduna düşer, video TikTok uygulamandaki gelen kutusuna gelir. Yani
en kötü durumda içerik kaybolmaz, sadece son tıklamayı sen yaparsın.

## Bilmen gereken riskler

Bu, belgelenmiş bir API değil — TikTok'un kendi arayüzünü sürüyoruz.
Bunun üç pratik sonucu var:

1. **Oturum düşer.** TikTok çerezleri genelde birkaç hafta dayanır.
   Düştüğünde iş net bir hatayla durur ve aşağıdaki giriş adımını
   tekrarlaman gerekir. Günlük **sağlık kontrolü** işi, düşmesine bir
   haftadan az kalınca uyarır.
2. **Arayüz değişir.** TikTok bir düğmenin yerini değiştirdiğinde iş
   "… bulunamadı" diyerek durur ve ekran görüntüsü bırakır. Düzeltme tek
   dosyada: `src/tiktok_studio/selectors.py`.
3. **Otomasyon fark edilebilir.** Bu yüzden işler günde birkaç kez çalışır,
   aynı anda iki oturum açılmaz ve tek çalışmada en fazla 3 video yüklenir.

Bu risklere karşı en iyi sigorta **zamanlama** kullanmaktır: video, paylaşım
gününden önce TikTok'a yüklenip TikTok'un kendi zamanlayıcısına bırakılır.
Paylaşım anında CI'ın çalışmasına da oturumun geçerli olmasına da gerek kalmaz.

## 1. Oturumu üret (kendi bilgisayarında)

```bash
pip install -r requirements.txt
python -m playwright install chromium
python tools/tiktok_studio_login.py
```

Bir tarayıcı açılır, TikTok'a normal şekilde giriş yaparsın (şifre, doğrulama
kodu — script hiçbirine karışmaz), Studio ana ekranını görünce terminale
dönüp Enter'a basarsın.

Script iki dosya bırakır:

- `.tiktok_studio_state.json` — yerel çalıştırmalar bunu kullanır (git'e girmez)
- `cerez.b64` — CI secret'ına yapıştıracağın değer

## 2. Secret'ı ekle

**GitHub:** Settings → Secrets and variables → Actions → New repository secret

| Ad | Değer |
|---|---|
| `TIKTOK_STUDIO_COOKIES` | `cerez.b64` dosyasının içeriği |

**GitLab:** Settings → CI/CD → Variables → **Masked** ve **Protected** işaretli.

Secret'ı ekledikten sonra `cerez.b64` dosyasını sil — hesabına tam erişim demek:

```bash
del cerez.b64
```

## 3. Doğrula

**GitHub:** Actions → *TikTok Studio* → Run workflow → `gorev: saglik`

**GitLab:** CI/CD → Pipelines → Run pipeline → `JOB=tiktok-saglik`

Çıktıda `✅ TikTok Studio oturumu geçerli.` görmen gerekiyor. Çerezin ne zaman
düşeceğini de yazar.

## 4. Zamanlamaları kur

GitHub'da `.github/workflows/tiktok-studio.yml` içindeki cron'lar hazır gelir.
GitLab'da Settings → CI/CD → **Pipeline schedules** altından dört zamanlama
tanımla:

| Ne zaman | Değişken | Yapar |
|---|---|---|
| Her gün 06:00 | `JOB=tiktok-saglik` | Oturum ayakta mı, çerez ne zaman düşecek |
| Her gün 06:20 | `JOB=tiktok-zamanla` | Yaklaşan postları TikTok'a planlar |
| Her gün 08:00 | `JOB=tiktok-analitik` | Analitiği `state/` altına yazar |
| Pazartesi 08:30 | `JOB=tiktok-yorumlar` | Yorumları toplar, yanıt taslağı üretir |

## Kullanım

### Post'u TikTok Studio'ya yönlendirme

Post dosyasının front matter'ında:

```yaml
---
platforms: [tiktok_studio]
media: posts/media/2026-08-20-arduino-seti.mp4
publish_at: 2026-08-20 10:00
---
```

`zamanla` işi bu postu paylaşım gününden önce TikTok'a yükler ve TikTok'un
zamanlayıcısına bırakır. Hemen yayınlanmasını istiyorsan `platforms` listesinde
bırakıp `zamanla` işini beklemeden `python -m src.tiktok_studio yukle <slug>
--hemen` diyebilirsin.

`tiktok` ve `tiktok_studio` ayrı platformlar — ikisini birden yazarsan video
iki kez gider.

### Komutlar

```bash
python -m src.tiktok_studio saglik              # oturum geçerli mi
python -m src.tiktok_studio zamanla --gun 7     # yaklaşan postları planla
python -m src.tiktok_studio zamanla --dry-run   # hiçbir şey yayınlamadan dene
python -m src.tiktok_studio yukle <slug>        # tek postu yükle
python -m src.tiktok_studio analitik            # analitiği kaydet
python -m src.tiktok_studio yorumlar            # yorumları topla, taslak üret
```

### Ayarlar (ortam değişkenleri)

| Değişken | Varsayılan | Ne yapar |
|---|---|---|
| `TIKTOK_STUDIO_COOKIES` | — | Oturum çerezi (base64) |
| `TIKTOK_STUDIO_KANAL` | — | Tarayıcıyı zorla: `chrome`, `msedge`. Boşsa sırayla paket Chromium → Chrome → Edge denenir |
| `TIKTOK_STUDIO_HEADFUL` | `false` | Tarayıcıyı görünür aç (hata ayıklama) |
| `TIKTOK_STUDIO_YAVASLIK` | `1` | Bekleme çarpanı; CI'da `1.5` |
| `TIKTOK_STUDIO_YEDEK_API` | `true` | Studio başarısız olursa API taslağına düş |
| `TIKTOK_STUDIO_LOG_DIR` | `logs/tiktok-studio` | Hata dökümleri |

## Bir şey bozulduğunda

**"BrowserType.launch: spawn UNKNOWN"** ya da Windows'un *"yan yana yapılandırma
doğru değil"* hatası → Chromium'un ihtiyaç duyduğu Microsoft Visual C++
çalışma zamanı eksik. Kur:

```bash
winget install Microsoft.VCRedist.2015+.x64
```

Otomasyon zaten paket Chromium açılmazsa kurulu Chrome'a, o da olmazsa Edge'e
kendiliğinden düşer — yani bu hata işi durdurmaz, sadece hangi tarayıcının
kullanıldığını değiştirir. Belirli bir tarayıcıyı zorlamak istersen
`TIKTOK_STUDIO_KANAL=chrome` verebilirsin, ama normalde gerekmez.

**"TikTok Studio oturumu düşmüş"** → 1. adımı tekrarla, secret'ı güncelle.

**"… bulunamadı"** → TikTok arayüzü değişmiş. İşin artifact'ındaki ekran
görüntüsünü aç, öğenin yeni halini gör, `src/tiktok_studio/selectors.py`
içindeki ilgili listeye yeni seçiciyi **ekle** (eskisini silme — farklı
sürümler farklı çalışıyor).

**"Zamanlama doğrulanamadı"** → Bu bir güvenlik freni: tarih/saat alanları
kurulamadığı için video yayınlanmadan durduruldu. Yoksa TikTok videoyu
o an yayınlardı. Yine `selectors.py` içindeki tarih/saat seçicilerine bak.

Hata ayıklarken tarayıcıyı görerek çalıştırmak en hızlısı:

```bash
set TIKTOK_STUDIO_HEADFUL=true
python -m src.tiktok_studio zamanla --dry-run
```

## Yorumlar hakkında

Otomasyon yorum **göndermiyor** — topluyor ve `content/yorum_taslaklari.md`
dosyasına "şu yoruma şu yanıt" biçiminde taslak yazıyor. Hesabın adına
herkese açık konuşan bir botun yanlış cevabı, geç cevaptan pahalıya patlar.

Hazır yanıtları `content/yorum_yanitlari.json` içinde düzenleyebilirsin:
yorumda geçen anahtar kelime hangi kurala denk gelirse o yanıt taslağa yazılır,
hiçbiri tutmazsa yorum "elle yanıtla" listesine düşer.

## Video üretimi

Elinde video yoksa ürün görsellerinden dikey video üretebilirsin:

```bash
python -m src.video_uretim --post 2026-08-20-senaryo-arduino-baslangic-seti
```

Carousel slide'larıyla aynı marka dilinde, 1080x1920, her karede yavaş
yakınlaşma. `ffmpeg` gerekiyor (Windows: `winget install Gyan.FFmpeg`).

### Kanca

Carousel'de tempoyu izleyici belirler — istediği slide'da durur. Videoda
tempoyu biz belirleriz ve ilk saniye kaydırılıp geçilmeyi belirler. Bu yüzden
video üretimi iki şey yapıyor:

**1. Her kare işine göre süre alır.** Dosya adındaki role bakar: hikaye
kareleri (`kanca`, `dert`, `hayal`) okunacak kadar durur, ürün fotoğrafları
(`urun`) hızlı geçer. Toplam süre 60 saniyeyi aşarsa hepsi aynı oranda kısalır.

| Kare | Süre |
|---|---|
| kanca | 2,8 sn |
| dert / hayal | 3,6 sn |
| cozum | 3,0 sn |
| kapak | 2,4 sn |
| urun | 1,9 sn |
| kapanis | 2,8 sn |

**2. Kancası olmayan videoya kanca ekler.** Senaryolu carousel'ler zaten
`01-kanca.jpg` ile açılıyor. Klasik carousel'ler düz kapakla açıldığı için
postun front matter'ına `tiktok_kanca:` satırı eklemen gerekiyor:

```yaml
tiktok_kanca: Kafandaki projeye aylardır başlayamadın mı?
```

Ya da tek seferlik denemek için:

```bash
python -m src.video_uretim --post <slug> --kanca "Kafandaki projeye aylardır başlayamadın mı?"
```

Kanca metni verilmezse üretim durmaz ama uyarı verir — ürün adını kanca diye
göstermek izleyiciyi durdurmadığı için otomatik bir kanca uydurmuyoruz.

Kanca karesinin üstündeki küçük etiket cümlenin tipine göre seçilir (soruya
"TANIDIK GELDİ Mİ?", temenniye "PEKİ YA ŞÖYLE OLSA?", düz cümleye "DURUM ŞU"
gibi). Beğenmezsen `tiktok_kanca_etiket:` ile kendin yazabilirsin.

GitHub'da Actions → *TikTok videosu üret* akışını elle çalıştırırsan üretilen
videoyu pull request olarak açar. Zamanlanmış değil, çünkü mp4 dosyaları
repoyu hızla şişirir — her videoyu görerek eklemek daha iyi.
