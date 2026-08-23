"""TikTok Studio arayüzündeki öğelerin seçicileri — tek dosyada toplandı.

TikTok Studio'nun resmi API'si yok, arayüzü de haber vermeden değişiyor.
Bir şey çalışmadığında kodun içinde seçici aramak yerine SADECE bu dosyayı
güncellemen yeterli olsun diye hepsi burada duruyor.

Her giriş bir liste: sırayla denenir, ilk görünen kullanılır. Böylece hem
Türkçe hem İngilizce arayüz, hem de eski/yeni sürümler birlikte desteklenir.

Seçici biçimi Playwright'ın kendi sözdizimi:
    "button:has-text('Post')"      → metni içeren buton
    "text=/Post|Yayınla/i"         → büyük/küçük harf duyarsız regex
    "input[type=file]"             → düz CSS
"""

from __future__ import annotations

# --- Sayfa adresleri ---------------------------------------------------------

ANASAYFA = "https://www.tiktok.com/tiktokstudio"
YUKLEME = "https://www.tiktok.com/tiktokstudio/upload"
ANALITIK = "https://www.tiktok.com/tiktokstudio/analytics"
YORUMLAR = "https://www.tiktok.com/tiktokstudio/comment"
ICERIK = "https://www.tiktok.com/tiktokstudio/content"

# Giriş yapılmamışsa TikTok bu adreslere yönlendiriyor.
GIRIS_ADRES_PARCALARI = ("/login", "/signup", "passport", "/foryou")

# --- Oturum kontrolü ---------------------------------------------------------

# Bunlardan biri görünüyorsa oturum düşmüş demektir.
GIRIS_ISARETLERI = [
    "text=/Log in to TikTok|TikTok'a giriş yap/i",
    "button:has-text('Log in')",
    "button:has-text('Giriş yap')",
]

# Bunlardan biri görünüyorsa Studio açılmış demektir.
STUDIO_ISARETLERI = [
    "text=/Upload|Yükle/i",
    "[data-e2e='upload-icon']",
    "a[href*='tiktokstudio/upload']",
]

# --- Yükleme sayfası ---------------------------------------------------------

# Yükleme arayüzü bazı sürümlerde iframe içinde geliyor.
YUKLEME_IFRAME = [
    "iframe[src*='upload']",
    "iframe[data-tt='Upload_index_iframe']",
]

DOSYA_GIRISI = [
    "input[type=file][accept*='video']",
    "input[type=file]",
]

# Video işlenirken görünen, yükleme bittiğinde kaybolan öğeler.
YUKLENIYOR = [
    "text=/Uploading|Yükleniyor/i",
    "[class*='progress'] [class*='bar']",
]

# Video hazır olduğunda görünenler.
YUKLEME_TAMAM = [
    "text=/Uploaded|Yüklendi/i",
    "text=/\\d+%/",
    "[class*='preview'] video",
    "video",
]

ACIKLAMA_ALANI = [
    "div[contenteditable='true'][role='combobox']",
    ".public-DraftEditor-content",
    "div[contenteditable='true']",
    "[data-e2e='video-caption'] div[contenteditable='true']",
]

# Hashtag/@ yazarken açılan öneri kutusu — Escape ile kapatılıyor.
ONERI_KUTUSU = [
    "[class*='mention-list']",
    "[class*='suggestion']",
]

# --- Zamanlama ---------------------------------------------------------------

# 20.08.2026: TikTok anahtardan (switch) RADIO'ya gecti ve etiketi
# "Zamanla" degil "Planla" oldu. Yeni yapi:
#   <label class="Radio__root"><input type="radio"> ... Planla</label>
ZAMANLA_ANAHTARI = [
    "label.Radio__root:has-text('Planla')",
    "label:has(input[type='radio']):has-text('Planla')",
    "label.Radio__root:has-text('Schedule')",
    "label:has(input[type='radio']):has-text('Schedule')",
    "label.Radio__root:has-text('Zamanla')",
    "text=/^Schedule$/i",
    "text=/^Zamanla$/i",
    "[data-e2e='schedule_switch']",
    "input[type='checkbox'][class*='switch']",
]

# 20.08.2026: alanlar salt-okunur oldu; tiklayinca panel aciliyor.
# Sirali: .scheduled-picker icindeki 1. input saat, 2. input tarih.
TARIH_ALANI = [
    ".scheduled-picker input.TUXTextInputCore-input >> nth=1",
    ".scheduled-picker input >> nth=1",
    "[class*='date-picker'] input",
    "input[placeholder*='YYYY']",
    "[class*='TUXDatePicker'] input",
]

SAAT_ALANI = [
    ".scheduled-picker input.TUXTextInputCore-input >> nth=0",
    ".scheduled-picker input >> nth=0",
    "[class*='time-picker'] input",
    "input[placeholder*='HH']",
]

# Yeni kaydirmali saat secici: sol sutun saat, sag sutun dakika.
SAAT_PANELI = ".tiktok-timepicker-time-picker-container"
SAAT_SUTUNU = ".tiktok-timepicker-option-text.tiktok-timepicker-left"
DAKIKA_SUTUNU = ".tiktok-timepicker-option-text.tiktok-timepicker-right"

# Takvim/saat açılır kutularındaki seçilebilir hücreler ({deger} doldurulur).
TAKVIM_GUNU = [
    ".calendar-wrapper span.day.valid:text-is('{deger}')",
    ".calendar-wrapper span.day:text-is('{deger}')",
    "[class*='calendar'] span:text-is('{deger}')",
    "[class*='day']:text-is('{deger}')",
]

# Takvim paneli ve ay gezinme (23.08.2026 arayuzu)
TAKVIM_PANELI = ".calendar-wrapper"
TAKVIM_AY_BASLIK = ".calendar-wrapper .month-title"
TAKVIM_YIL_BASLIK = ".calendar-wrapper .year-title"
TAKVIM_ILERI_OK = ".calendar-wrapper .month-header-wrapper .arrow >> nth=1"

SAAT_SECENEGI = [
    "[class*='time-picker'] div:text-is('{deger}')",
    "[class*='hour'] div:text-is('{deger}')",
]

# --- Yayınlama ---------------------------------------------------------------

YAYINLA_BUTONU = [
    "button[data-e2e='post_video_button']",
    "button:has-text('Post')",
    "button:has-text('Yayınla')",
    "button:has-text('Schedule')",
    "button:has-text('Zamanla')",
]

YAYIN_TAMAM = [
    "text=/Your video is being uploaded|Videon yükleniyor/i",
    "text=/Manage your posts|Gönderilerini yönet/i",
    "text=/scheduled|zamanlandı/i",
    "[class*='success']",
]

# --- Analitik ----------------------------------------------------------------

# Analitik sayfasının kendi arka plan isteklerini yakalıyoruz; DOM okuması
# yedek plan. Bu parçalar geçen istekler analitik verisi taşıyor demektir.
ANALITIK_ISTEK_PARCALARI = (
    "/aweme/v2/data/insight/",
    "/tiktok/v1/analytics/insights/",
    "insight",
)

# --- Yorumlar ----------------------------------------------------------------

# Yorumlar ekrandan okunuyor. Ağ dinlemesi denendi ama Studio yorum listesini
# ayrı bir JSON ucundan çekmiyor; her yanıtın gövdesini indirip aramak da çok
# pahalıydı. Ekranda ise yapı düzenli:
#   [kullanıcı, '·', zaman, yorum metni, beğeni, 'Yanıtla', 'Sil']
# Satırı "Yanıtla" bağlantısından bulup yukarı doğru çıkıyoruz.
YORUM_OKUYUCU_JS = r"""
() => {
  const tetikler = [...document.querySelectorAll('div,span,button,a')].filter(
    e => e.children.length === 0 && /^(yanıtla|reply)$/i.test(e.textContent.trim())
  );

  const cikti = [];
  for (const t of tetikler) {
    let kok = t;
    for (let i = 0; i < 8 && kok.parentElement; i++) {
      kok = kok.parentElement;
      const satir = (kok.innerText || '').split('\n').map(s => s.trim()).filter(Boolean);
      const n = satir.indexOf('·');
      if (n > 0 && satir.length > n + 2) {
        cikti.push({
          yazar: satir[n - 1],
          zaman: satir[n + 1],
          metin: satir[n + 2],
          begeni: satir[n + 3] || '0',
        });
        break;
      }
    }
  }
  return cikti;
}
"""

DAHA_FAZLA_YORUM = [
    "text=/Load more|Daha fazla yükle/i",
    "button:has-text('More')",
]
