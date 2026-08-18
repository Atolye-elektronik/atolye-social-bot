# Video arka plan müziği

Buraya `.mp3` (ya da `.m4a`, `.wav`) koyarsan `src/video_uretim.py` üretilen
videolara kendiliğinden arka plan müziği ekler. Klasör boşsa video sessiz
kalır — hata vermez.

Nasıl seçiliyor: post adına göre sabit bir seçim yapılır. Yani aynı post her
üretimde aynı parçayı alır, ama farklı postlar farklı parçalara denk gelir;
tüm videolarda aynı melodi çalmaz.

Ses seviyesi varsayılan olarak %25'e kısılır ve videonun son 2 saniyesinde
yumuşakça biter. Değiştirmek için:

```bash
set VIDEO_MUZIK_SES=0.4
```

## Telif uyarısı

Buraya koyduğun parçanın kullanım hakkı sende olmalı. TikTok yüklenen
videolarda müzik telif kontrolü yapıyor (yükleme ekranında "Müzik telif hakkı
kontrolü" olarak görünür); hak sahibi olmadığın bir parça videonun sessize
alınmasına ya da kaldırılmasına yol açabilir.

İki güvenli kaynak:

- **YouTube Ses Kitaplığı** — studio.youtube.com > *Ses kitaplığı*. Ücretsiz,
  telifsiz, indirilebilir. Şu an bu klasördeki parçaların hepsi buradan geldi.
- **TikTok'un kendi kütüphanesi** — Studio > Araçlar > *Telifsiz sesler*.

## Şu an klasörde ne var

2026-08-17'de YouTube Ses Kitaplığı'ndan indirildi. Hepsi **Neşeli** ruh
halinde ve biri hariç **Dans ve Elektronik** türünde — marka tonu elektronik/
maker içeriğine uysun diye böyle seçildi:

| Parça | Tür | Süre |
|---|---|---|
| After all this time | Dans ve Elektronik | 2:37 |
| All In | Dans ve Elektronik | 3:07 |
| Back To The Start | Dans ve Elektronik | 2:30 |
| Eyes | Dans ve Elektronik | 3:10 |
| The Theme | Dans ve Elektronik | 2:57 |
| Time of your life | Dans ve Elektronik | 2:44 |
| Paradise | Pop (Mutlu) | 2:55 |

Lisans türü sütunu hepsinde YouTube Ses Kitaplığı lisansını gösteriyordu
(ilişkilendirme gerektiren CC BY parçalar ayrıca işaretlenir; bunlarda yoktu).

**Sınırı bil:** bu lisans YouTube için nettir. Aynı mp4 TikTok ve Reels'e de
gidiyor ve oralarda telif tarayıcıları kendi kurallarıyla çalışıyor. Şimdiye
kadar sorun çıkmadıysa devam; bir video sessize alınırsa o platform için
TikTok'un kendi kütüphanesinden parça koy.

**Gerçekten "viral" ses istiyorsan:** trend olan parçalar telifli, bu klasöre
konamaz. Platformda öne çıkmanın yolu videoya müzik gömmek değil, sesi
platformun kendi arayüzünden seçmek.

## Seçilen yol: sesi yükleme sonrası platformda seç

2026-08-17'den itibaren videolar **sessiz** üretiliyor; ses YouTube'a yüklendikten
sonra elle seçiliyor. Sessiz üretmek için:

```bash
python -m src.video_uretim --post <slug> --sessiz
```

`--sessiz`, bu klasör dolu olsa bile müzik eklemez. Bayrağı vermezsen eski
davranış sürer (klasörden bir parça seçilip videoya gömülür) — TikTok/Reels
için gömülü müzik isteyip istemediğine göre karar ver.

YouTube'da ses ekleme yeri: **Studio → video → Düzenleyici → Ses**. Parça
listesinden seçip Kaydet'e basıyorsun; yayınlanmış videolarda da çalışıyor.
Not: oradaki liste de aynı telifsiz kitaplık, yani trend/viral ses değil.
Shorts'ta trend sesi ancak YouTube **mobil uygulamasının** Shorts oluşturma
akışından eklenebiliyor.
