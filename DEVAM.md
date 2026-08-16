# Nerede kaldık — devam notu

Son güncelleme: 16 Ağustos 2026. Bu belge, çalışmayı başka bir makinede
kaldığı yerden sürdürebilmek için yazıldı.

Okul açılışına yaklaşık 3 hafta var. Kampanyanın kritik penceresi eylülün
ilk iki haftası: malzeme listeleri o zaman kesinleşiyor.

---

## 1. Depoyu kur

GitHub erişimi kapalı (aşağıda anlatılıyor), çalışan uzak sunucu GitLab:

```bash
git clone https://gitlab.com/atolye-elektronik-group/atolye-social-bot.git
cd atolye-social-bot
git checkout claude/atolyeelektronik-marketing-51t98q
pip install -r requirements.txt
pip install openpyxl playwright   # rapor ve görsel üretimi için
```

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

## 3. Senin yapman gereken üç iş

**a) Taslak temayı yayınla**

Shopify'da `Atölye — kargo 1200 + tam başlık (taslak)` adlı tema hazır ve
önizlenmeyi bekliyor. İçinde:

- Duyuru barı 1.500 → **1.200 TL**
- Kampanyalar sayfası 1.500 → **1.200 TL** (iki yerde)
- Sepet ilerleme çubuğu eşiği `150000` → **`120000`** kuruş
- Ürün başlıklarının iki satırda kesilmesini engelleyen CSS

Canlı temaya yazmak güvenlik gereği engelli olduğu için taslak üzerinden
gidildi. Önizle, iyiyse yayınla.

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

Gönderilen: Antalya 13 (ilin tamamı), Mersin 7, Burdur 3, Isparta 1.
**Sıfır geri dönüş.** Bu önemli, çünkü adresleri kurum kodundan türettik
(`124137@meb.k12.tr` biçiminde) ve bu bir varsayımdı — tuttuğu doğrulandı.

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
# Devlet okulları (MEB kurum dizininden)
python -m src.okul_listesi                       # 2.413 MTAL, 81 il
python -m src.okul_listesi --tur mesem --cikti pazarlama/mesem.csv    # 455
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

**Elde edilen sayılar:** 2.413 MTAL (447'sinde elektrik-elektronik, 663'ünde
bilişim, 794'ünde ikisinden biri) · 455 MESEM · 371 BİLSEM · 291 özel MTAL ·
78 özel robotik kursu · 223 Instagram hesabı.

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
uygulamaya izin vermek yeterli değil, anahtarın kendisi lazım. Kod hazır:

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

---

## 8. Açık kalan kararlar

- E-posta kampanyasında hangi illere, hangi tempoda devam edilecek?
  (Bölge listesi `pazarlama/okullar-1parti.csv`, 57 okul — 24'ü gitti.)
- Instagram karuseli anahtarla mı atılacak, elle mi?
- Instagram hesap listesi 223'te duruyor; 2.413 okulun küçük bir kısmı.
  Genişletmenin en verimli sırası: BİLSEM → robotik kursları → MYO → MTAL.
- Robotik kursları segmenti (78 özel kurs + 50 Instagram hesabı) henüz hiç
  temas edilmedi. Sezon dışı satışın asıl kaynağı burası: okul eylülde alıp
  susuyor, kurs yıl boyu malzeme tüketiyor.
