# Nerede kaldık — devam notu

Son güncelleme: 16 Ağustos 2026 (ikinci oturum). Bu belge, çalışmayı başka
bir makinede kaldığı yerden sürdürebilmek için yazıldı.

**Bu oturumda değişenler:** taslak temanın zaten yayında olduğu görüldü
(bölüm 3a düştü) · `okul_listesi` bozuktu, düzeltildi (bölüm 7) · üç liste
yeniden üretildi · kampanyaya devam planı sayılarla yazıldı (bölüm 8).

Okul açılışına yaklaşık 3 hafta var. Kampanyanın kritik penceresi eylülün
ilk iki haftası: malzeme listeleri o zaman kesinleşiyor.

---

## 1. Depoyu kur

GitHub erişimi kapalı (aşağıda anlatılıyor), çalışan uzak sunucu GitLab.
Proje **public** — klonlamak için kimlik doğrulaması gerekmiyor:

```bash
git clone -b claude/atolyeelektronik-marketing-51t98q \
  https://gitlab.com/atolye-elektronik-group/atolye-social-bot.git
cd atolye-social-bot
pip install -r requirements.txt
pip install openpyxl playwright markdown   # rapor, görsel ve devam notu için
python -m playwright install chromium      # karusel + PDF için, ayrı adım
```

Windows'ta (PowerShell) sanal ortamla:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt openpyxl playwright markdown
.\.venv\Scripts\python.exe -m playwright install chromium
```

`requirements.txt` bilerek yalın tutuldu (yalnızca çalışma zamanı bağımlılığı);
`openpyxl`, `playwright` ve `markdown` sadece rapor/görsel/belge üretiminde
gerekiyor.

**Bu belgenin PDF ve HTML sürümleri artık elle yazılmıyor.** DEVAM.md'yi
değiştirdikten sonra çalıştır, `pazarlama/devam.html` ve
`pazarlama/devam-notu.pdf` yeniden üretilsin:

```bash
python tools/devam_pdf.py
```

**Windows tuzağı:** `python` komutu Microsoft Store kısayoluna düşüp
"Python bulunamadı" diyebilir; gerçek kurulum
`%LOCALAPPDATA%\Programs\Python\Python312\python.exe` altındadır. PATH ile
uğraşmak yerine doğrudan bu yolu çağır.

**Önemli:** hedef listeleri (`pazarlama/*.csv`, `*.xlsx`) `.gitignore` içinde,
yani klonda gelmezler. Kurum e-postası ve telefonu içerdikleri için bilerek
böyle. Tek komutla yeniden üretiliyorlar — bölüm 5'e bak.

Gönderim kaydı (`state/okul_gonderilen.json`) **repoda**, çünkü içinde adres
değil adresin özeti var. Yani klonladığında daha önce yazdığın okullara
tekrar yazmazsın.

---

## 2. Mağazada canlı olanlar — dokunmaya gerek yok

| Ne | Durum |
|---|---|
| Sınıf paketi ürünleri | Temrin Defteri ve İş Dosyası, 3'er varyant, 6 satış kanalında yayında |
| Fiyatlar | Tekli 85 ₺ · 10'lu 833 ₺ (%2) · 20'li 1.649 ₺ (%3) · 30'lu 2.473,50 ₺ (%3) |
| Koleksiyonlar | "Defterler" ve "Defterler ve Meslek Lisesi Setlerimiz" içine eklendi |
| Kargo eşiği | 1.200 ₺ — hem teslimat tarifesinde hem "ÜCRETSİZ KARGO" otomatik indiriminde |
| Okul siparişi sayfası | atolyeelektronik.com/pages/okul-siparisi |
| Fiyat listesi PDF | Shopify CDN'de, herkese açık kalıcı adres (bölüm 6) |

Sınıf paketlerinde stok takibi **kapalı** — paketler aynı fiziksel defterden
çıkıyor, ayrı stok tutmak yanlış sayı gösterirdi. Eylül öncesi fiziksel stok
tazelemeyi unutma.

---

## 3. Senin yapman gereken işler

**a) Taslak temayı yayınla — ✅ YAPILDI**

`Atölye — kargo 1200 + tam başlık (taslak)` teması artık `MAIN` rolünde,
yani canlı. Adında hâlâ "(taslak)" yazıyor, yanıltıcı — istersen Shopify'dan
yeniden adlandır. İçindekilerin hepsi canlıda doğrulandı (16 Ağustos 2026):

- Duyuru barı: "**1.200 TL** üzeri kargo bedava" ✓
- Kampanyalar sayfası: "1.200 TL Üzeri Ücretsiz Kargo" ✓, hiçbir yerde 1.500 kalmamış
- `templates/cart.liquid` → `shipping_threshold = 120000` kuruş ✓
- Teslimat tarifesi: 0–1.199,99 ₺ → 127 ₺ · 1.200 ₺ ve üzeri → 0 ₺ ✓
- "ÜCRETSİZ KARGO" otomatik indirimi: ACTIVE, alt sınır 1.200 ₺ ✓
- Sınıf paketi varyantları: `tracked: false` — stok 0 görünse de satılabilir ✓

**b) Terk edilmiş ödeme e-postasını aç**

Shopify → Ayarlar → Bildirimler → Terk edilmiş ödeme. API'de karşılığı yok,
elle açılması gerekiyor. 30 saniyelik iş ama önemli: 60 günde 14.100 ₺'lik
terk edilmiş sepet birikmişti, tamamlanan siparişlerin dört katı.

**c) GitHub erişimini aç**

`atolyeelektronik07-cyber` organizasyonu için Claude GitHub App bağlantısı
kurulmalı: https://claude.ai/admin-settings/claude-in-slack

Şu an hem okuma hem yazma 403 veriyor:
> GitHub access is not enabled for this session.

---

## 4. E-posta kampanyası — 24 okul gönderildi

Gönderilen: Antalya 13, Mersin 7, Burdur 3, Isparta 1.
**Sıfır geri dönüş.** Bu önemli, çünkü adresleri kurum kodundan türettik
(`124137@meb.k12.tr` biçiminde) ve bu bir varsayımdı — tuttuğu doğrulandı.

**Düzeltme:** notun önceki hâlinde "Antalya 13 (ilin tamamı)" yazıyordu; bu
yanlış. Tam liste yeniden üretilince Antalya'da **22 genel MTAL daha**
gönderilmemiş çıktı (Mersin 26, Isparta 13, Burdur 6). O rakam muhtemelen
`okullar-1parti.csv` içindeki Antalya satırlarını sayıyordu, ilin tamamını
değil. Yani "bitmiş" saydığın iller bitmemiş — bölüm 8'e bak.

Gönderim Gmail üzerinden yapıldı (atolyeelektronik07@gmail.com). Yerelde
betikle sürdürmek için Gmail **uygulama şifresi** gerekiyor:

```bash
export SMTP_USER="atolyeelektronik07@gmail.com"
export SMTP_PASSWORD="uygulama-sifresi"     # normal parolan değil
export IMZA_ADI="Adın Soyadın"              # imzada görünecek isim

python -m src.okul_daveti --liste pazarlama/okullar-hedef.csv --dry-run
python -m src.okul_daveti --liste pazarlama/okullar-hedef.csv --limit 25
```

Betik ekli PDF ile gönderiyor. Gmail üzerinden gönderirken bağlantı
kullanıldı çünkü ek her mesaja ayrı ayrı gömülemiyordu; yerelde SMTP ile
ek sorunsuz gidiyor.

**Tempo:** günde 20–30'u geçme. Soğuk kampanyada Gmail hesabından hızlanmak
teslim edilebilirliği düşürür ve sonraki yüzlerce e-posta spam'e düşer.

**Metinden mekatronik çıkarıldı** (senin isteğinle). Şablon
`src/okul_daveti.py` içinde `GOVDE` sabitinde.

---

## 5. Listeler nasıl yeniden üretilir

```bash
# Devlet okulları (MEB kurum dizininden) — üçü de 16.08.2026'da yeniden üretildi
python -m src.okul_listesi                       # 2.414 MTAL, 81 il (~6 dk)
python -m src.okul_listesi --tur mesem --cikti pazarlama/mesem.csv    # 457
python -m src.okul_listesi --tur bilsem --cikti pazarlama/bilsem.csv  # 371

# Telefon, adres, varsa Instagram ekle
python -m src.okul_iletisim --liste pazarlama/okullar.csv

# Alan (bölüm) tespiti — okul site haritalarından
python -m src.okul_bolum --liste pazarlama/okullar.csv

# Özel kurumlar (ayrı dizin, e-posta vermiyor — telefon ve adres var)
python -m src.ozel_kurumlar --tur mtal --cikti pazarlama/ozel-mtal.csv        # 291
python -m src.ozel_kurumlar --tur robotik --cikti pazarlama/ozel-robotik.csv  # 78

# Hepsini tek Excel'de topla
python -m src.rapor
```

Tam tarama yaklaşık 1–1,5 saat sürüyor (dizinlere yük bindirmemek için
aralarında bekleme var). `okul_iletisim` ve `okul_bolum` kesilirse kaldığı
yerden devam eder.

**Elde edilen sayılar (16.08.2026 taraması):** 2.414 MTAL — 1.511'i genel,
903'ü dar alan (ticaret/turizm/sağlık/imam hatip…) · 457 MESEM · 371 BİLSEM.
Önceki taramadan devreden bölüm sayıları: 447 elektrik-elektronik, 663
bilişim, 794 ikisinden biri. Ayrıca 291 özel MTAL · 78 özel robotik kursu ·
223 Instagram hesabı.

`okul_listesi` çıktısındaki **`oncelik` sütunu** kampanyanın sıralama anahtarı:
`genel` olanlarda elektrik-elektronik atölyesi olma ihtimali yüksek, `dar alan`
olanlarda düşük. Önce `genel` olanlara git.

---

## 6. Instagram — karusel hazır, anahtar eksik

5 slaytlık fiyat listesi karuseli üretildi ve CDN'e yüklendi:

```
https://cdn.shopify.com/s/files/1/0801/9692/7717/files/ig-karusel-1.png?v=1786875177
https://cdn.shopify.com/s/files/1/0801/9692/7717/files/ig-karusel-2.png?v=1786875177
https://cdn.shopify.com/s/files/1/0801/9692/7717/files/ig-karusel-3.png?v=1786875178
https://cdn.shopify.com/s/files/1/0801/9692/7717/files/ig-karusel-4.png?v=1786875177
https://cdn.shopify.com/s/files/1/0801/9692/7717/files/ig-karusel-5.png?v=1786875177
```

Fiyat listesi PDF'i:
```
https://cdn.shopify.com/s/files/1/0801/9692/7717/files/Atolye-Elektronik-Okul-Fiyat-Listesi.pdf
```

Kaynak dosyalar `pazarlama/karusel/` içinde; fiyat değişirse HTML'i düzenleyip
yeniden üret:

```bash
python - <<'EOF'
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width":1080,"height":1080})
    for i in range(1,6):
        pg.goto(f"file://{__import__('pathlib').Path('pazarlama/karusel').resolve()}/{i}.html",
                wait_until="networkidle")
        pg.screenshot(path=f"pazarlama/karusel/karusel-{i}.png")
    b.close()
EOF
```

**Gönderim için gereken:** `META_ACCESS_TOKEN` ve `IG_USER_ID`. Meta panelinde
uygulamaya izin vermek yeterli değil, anahtarın kendisi lazım. `IG_USER_ID`
sabit ve elimizde; eksik olan tek şey token.

Token'ın yeri: Meta Business Suite → Ayarlar → Kullanıcılar → **Sistem
kullanıcıları** → *Jeton oluştur*. Türkçe arayüzde "access token" değil
**"jeton"** yazıyor — bir kez bu yüzden bulunamadı. Süre "Süresi dolmaz"
seçilecek. Gereken izinler: `pages_manage_posts`, `pages_read_engagement`,
`pages_show_list`, `instagram_basic`, `instagram_content_publish`.
Token'ı sohbete yapıştırma, doğrudan GitLab CI değişkenine gir.

Karusel üretim zinciri 16.08.2026'da uçtan uca çalıştırılıp doğrulandı
(5 slayt, altbilgi kırpılmadan, fiyatlar Shopify varyantlarıyla birebir).
CDN'deki 5 görselin ve fiyat listesi PDF'inin hepsi 200 dönüyor. Kod hazır:

```bash
export META_ACCESS_TOKEN=...
export IG_USER_ID=...
python -c "
from src import instagram
gorseller = [f'https://cdn.shopify.com/s/files/1/0801/9692/7717/files/ig-karusel-{i}.png?v=1786875177' for i in range(1,6)]
gorseller[2] = gorseller[2].replace('v=1786875177','v=1786875178')
print(instagram.publish_carousel(open('pazarlama/ig-altyazi.txt').read(), gorseller))
"
```

DM metinleri `pazarlama/instagram-dm-metinleri.md` içinde — üç segment için
ayrı yazıldı. **Toplu DM atma:** Instagram bunu yakalıyor ve hesabın
kilitlenebiliyor. Günde 10–15, her mesajda okula özel bir cümle.

Sıra: bölüm hesapları (4) → elektrik-elektronik teyitli okullar (29) →
robotik kursları (50).

---

## 7. Öğrenilen tuzaklar — tekrar yaşamamak için

- **Depo sığ klon.** GitLab sığ geçmişi reddediyor. Çözüm: `git fast-export |
  git fast-import` ile tam geçmişli bir ayna kurup oradan push etmek. Bu
  yüzden GitLab'daki commit numaraları yereldekinden farklı; içerik aynı.
- **MEB özel kurumlar dizini sayfa başına 250 kayıt gösteriyor.** Sayfalama
  takip edilmezse büyük iller eksik çıkıyor (İstanbul 2 görünüyordu, 8'di).
- **Python'da `"İ".lower()`** birleşik noktalı bir `i` üretiyor ve düz `"ilçe"`
  ile eşleşmiyor. Tablo başlığı eşlerken sadeleştirme şart.
- **Okul sitelerinde bölüm tespiti** ana sayfadan yapılmaz: MEB altbilgisindeki
  "MEB Bilişim Sistemleri" bağlantısı her okulda bilişim bölümü varmış gibi
  gösteriyor. Doğru kaynak `/tema/siteharitasi.php`.
- **Chromium'un `--screenshot` bayrağı** yerleşim oturmadan yakalayabiliyor;
  altbilgi kırpılıyordu. Playwright ile alınca düzeldi.
- **Özel MESEM diye bir segment yok** — Türkiye genelinde tek kurum var.
- **MEB dizini sayaçları metin döndürüyor.** `recordsFiltered` artık `"64"`
  gibi geliyor, sayı değil. `okul_listesi` bunu `int` ile karşılaştırdığı için
  ilk ilde `TypeError` verip 81 ilin tamamını düşürüyordu (16.08.2026'da
  düzeltildi). `topla()` içindeki il bazlı `except` bilerek genişletilmedi:
  bu hata sessizce yutulsaydı çıktı boş bir CSV olacak, taramanın koptuğu
  fark edilmeyecekti.
- **Playwright'ın tarayıcısı ayrı kuruluyor.** `pip install playwright`
  yetmiyor; `python -m playwright install chromium` da çalıştırılmalı, yoksa
  karusel üretimi çalışma anında patlıyor.

---

## 8. E-posta kampanyası — devam planı

### Sıkışan aritmetik

Bunu önce görmek gerekiyor, çünkü planın tamamını belirliyor:

| | |
|---|---|
| Gönderilmemiş genel MTAL | **1.490** |
| Günlük üst sınır (teslim edilebilirlik) | 25 |
| Pencerenin kapanışı | ~8 Eylül (malzeme listeleri kesinleşiyor) |
| Kalan gün | 23 |
| **Gönderilebilecek toplam** | **~575** |

Havuz 1.490, bütçe 575. **Hepsine yetişmiyor.** Dolayısıyla asıl kaldıraç
tempoyu artırmak değil, doğru %40'ı seçmek.

### Bu yüzden önce bölüm taraması

`python -m src.okul_bolum --liste pazarlama/okullar.csv` (~1–1,5 saat)
1.490'ı, elektrik-elektronik veya bilişim bölümü **teyitli** ~794'e indiriyor.
575 e-postalık bütçeyi 794 kişilik bir havuzda harcamak, 1.490'lık havuzda
harcamaktan belirgin biçimde iyi. Gönderime başlamadan bunu çalıştır.

### Haftalık sıra

Sıra, ilin okul yoğunluğuna ve lojistik yakınlığa göre. Büyük iller **öne**
alındı, çünkü eylülün ilk haftasına kalırlarsa liste zaten kesinleşmiş olur.

| Hafta | Tarih | Adet | İller |
|---|---|---|---|
| 1 | 17–23 Ağu | 175 | Antalya 22 · Mersin 26 · Isparta 13 · Burdur 6 (başlanan iller bitsin) + Adana 28 · Hatay 27 · Konya 46 |
| 2 | 24–30 Ağu | 175 | İstanbul 172 |
| 3 | 31 Ağu–6 Eyl | 175 | Ankara 93 · İzmir 82 |
| 4 | 7–8 Eyl | 50 | İzmir kalanı 9 · Bursa 41 |

Kalan büyük iller (Kocaeli 40, Manisa 32, Şanlıurfa 30, Balıkesir 29,
Gaziantep 28, Diyarbakır 27, Kayseri 27, Samsun 27, Tekirdağ 23, Trabzon 23…)
pencereye yetişmiyor. Bunlar **ikinci dalga**: ekim–kasımda "ikinci dönem
malzeme planlaması" temasıyla yazılır. Sezon dışı temas kaybedilmiş temas
değil, sadece farklı bir mesaj gerektiriyor.

Komut (ilk 25'i denemek için):

```bash
python -m src.okul_daveti --liste pazarlama/okullar.csv --dry-run
python -m src.okul_daveti --liste pazarlama/okullar.csv --limit 25
```

`state/okul_gonderilen.json` tekrarı kendisi engelliyor; il sırasını tutturmak
için listeyi ile göre süzüp `--liste` olarak vermen yeterli.

### Karar gerektiren tek şey

Tempoyu 25'te tutup ~575'te mi kalınacak, yoksa ikinci bir gönderen adres
(`info@atolyeelektronik.com`, ayrı itibar havuzu) açılıp günlük 50'ye mi
çıkılacak? İkincisi kapsamı iki katına çıkarır ama yeni bir alan adının
ilk soğuk kampanyası ısıtılmadan başlarsa spam'e düşme riski taşır. Riski
almadan yapılacak hâli: yeni adresi 1–2 hafta düşük hacimle ısıtmak — ki bu
da tam olarak elimizde olmayan süre.

---

## 9. Diğer açık kararlar

- Instagram karuseli anahtarla mı atılacak, elle mi? (Görseller ve altyazı
  hazır, CDN'de erişilebilir; eksik olan tek şey `META_ACCESS_TOKEN`.)
- Instagram hesap listesi 223'te duruyor; 2.414 okulun küçük bir kısmı.
  Genişletmenin en verimli sırası: BİLSEM → robotik kursları → MYO → MTAL.
- Robotik kursları segmenti (78 özel kurs + 50 Instagram hesabı) henüz hiç
  temas edilmedi. Sezon dışı satışın asıl kaynağı burası: okul eylülde alıp
  susuyor, kurs yıl boyu malzeme tüketiyor. Yukarıdaki "ikinci dalga" ile
  aynı takvime denk geliyor — ekimde birlikte ele alınabilir.
