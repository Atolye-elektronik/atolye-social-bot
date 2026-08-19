"""Pinterest arayüzündeki öğelerin seçicileri — tek dosyada toplandı.

Pinterest'in pin oluşturma ekranı haber vermeden değişiyor. Bir şey
çalışmadığında kodun içinde seçici aramak yerine SADECE bu dosyayı
güncellemen yeterli olsun diye hepsi burada duruyor.

Her giriş bir liste: sırayla denenir, ilk görünen kullanılır. Böylece hem
Türkçe hem İngilizce arayüz, hem de eski/yeni sürümler birlikte desteklenir.
`data-test-id` seçicileri önce geliyor — Pinterest bunları metinlerden daha
seyrek değiştiriyor.

Seçici biçimi Playwright'ın kendi sözdizimi:
    "button:has-text('Kaydet')"      → metni içeren buton
    "text=/Save|Kaydet/i"            → büyük/küçük harf duyarsız regex
    "input[type=file]"               → düz CSS
"""

from __future__ import annotations

# --- Sayfa adresleri ---------------------------------------------------------

ANASAYFA = "https://www.pinterest.com/"
# Pin oluşturma ekranının iki adı var; yenisi önce denenir.
PIN_OLUSTUR = "https://www.pinterest.com/pin-creation-tool/"
PIN_OLUSTUR_ESKI = "https://www.pinterest.com/pin-builder/"

# Giriş yapılmamışsa Pinterest bu adreslere yönlendiriyor.
GIRIS_ADRES_PARCALARI = ("/login", "/signup", "/business/login")

# Oturumu taşıyan çerez — ömrü de bununla ölçülüyor.
OTURUM_CEREZLERI = ("_pinterest_sess",)

# Girişin tamamlandığını SADECE bu söyler: `_auth` 1 olur.
# `_pinterest_sess` giriş yapmamış ziyaretçiye de veriliyor, ona bakarak
# "giriş oldu" demek yanlış (bir kez bu yüzden boş oturum kaydedildi).
GIRIS_CEREZI = "_auth"
GIRIS_CEREZ_DEGERI = "1"

# --- Oturum kontrolü ---------------------------------------------------------

# Bunlardan biri görünüyorsa oturum düşmüş demektir.
GIRIS_ISARETLERI = [
    "[data-test-id='login-button']",
    "[data-test-id='simple-login-button']",
    "button:has-text('Giriş yap')",
    "button:has-text('Log in')",
    "text=/Pinterest'e giriş yap|Log in to Pinterest/i",
]

# Bunlardan biri görünüyorsa giriş yapılmış demektir.
GIRISLI_ISARETLERI = [
    "[data-test-id='header-profile']",
    "[data-test-id='header-accounts-options-button']",
    "[data-test-id='business-account-switcher']",
]

# Profil sayfasına giden bağlantı — panoları oradan okuyoruz.
PROFIL_BAGLANTISI = [
    "[data-test-id='header-profile'] a",
    "a[aria-label*='Profil' i]",
]

# Panolar profilin "Kaydedilenler" sekmesinde duruyor (varsayılan sekme
# "Oluşturulanlar", orada pano yok).
PANO_SEKMESI = "_saved/"

# Pano kartlarının test-id'si panonun adını taşıyor:
#     data-test-id="boardCard-Arduino ve Robotik Projeler"
PANO_KARTI_ONEKI = "boardCard-"
PANO_KARTI = ["[data-test-id^='boardCard-']"]

# --- Pin oluşturma ekranı ----------------------------------------------------
#
# Aşağıdakiler 17.08.2026'da canlı arayüzden okundu. Pinterest'in kendi
# adlandırması "storyboard" — pin taslağı ekranının iç adı bu.

# Ekranın açıldığını gösteren işaretler.
OLUSTURMA_ISARETLERI = [
    "[data-test-id='storyboard-draft-upload-container']",
    "[data-test-id='storyboard-upload-input']",
    "input[type=file]",
    "text=/Medyanızı yükleyin|Upload your media/i",
]

DOSYA_GIRISI = [
    "[data-test-id='storyboard-upload-input'] input[type=file]",
    "input[type=file][accept*='image']",
    "input[type=file]",
]

# Görsel yüklenirken görünen, bitince kaybolan öğeler.
YUKLENIYOR = [
    "text=/Yükleniyor|Uploading/i",
    "div[role='progressbar']",
]

# Yükleme bittiğinde beliren önizleme / kayıt onayı.
ONIZLEME = [
    "[data-test-id='storyboard-thumbnail']",
    "[data-test-id='storyboard-pin-card-item']",
    "[data-test-id='story-pin-image-block']",
    "[data-test-id='saving-status-saved']",
]

BASLIK_ALANI = [
    "#storyboard-selector-title",
    "[data-test-id='storyboard-title-field-container'] textarea",
    "[data-test-id='storyboard-title-field-container'] input",
]

# Açıklama bir contenteditable (zengin metin) alanı — value atanamıyor,
# tıklayıp klavyeden yazmak gerekiyor.
ACIKLAMA_ALANI = [
    "[data-test-id='storyboard-description-field-container'] [contenteditable='true']",
    "[data-test-id='editor-with-mentions'] [contenteditable='true']",
    "[data-test-id='comment-editor-container'] [contenteditable='true']",
]

LINK_ALANI = [
    "#WebsiteField",
    "[data-test-id='storyboard-selector-link'] input",
    "input[placeholder*='Bağlantı' i]",
]

# --- Pano seçimi -------------------------------------------------------------
#
# Pano seçici, görsel yüklenene kadar aria-disabled=true duruyor —
# yükleme bitmeden tıklamayı deneme.

PANO_DUGMESI = [
    "[data-test-id='board-dropdown-select-button']",
    "[data-test-id='storyboard-selector-board'] div[role=button]",
]

PANO_ARAMA = [
    "#pickerSearchField",
    "[data-test-id='search-boards-field-container'] input",
    "input[aria-label*='Panolarınızda ara' i]",
]

# Pano satırının kendi test-id'si panonun adını taşıyor:
#     data-test-id="board-row-Arduino ve Robotik Projeler"
# Bu yüzden adı biçimlendirerek doğrudan seçebiliyoruz.
PANO_SATIRI_KALIBI = "[data-test-id='board-row-{ad}']"

# Ada göre bulunamazsa listedeki herhangi bir satır.
PANO_SATIRI = [
    "[data-test-id^='board-row-']",
    "[data-test-id='boardWithoutSection']",
]

PANO_LISTESI = ["[data-test-id='board-picker-flyout']"]

# --- Yayınlama ---------------------------------------------------------------

KAYDET_DUGMESI = [
    "[data-test-id='storyboard-creation-nav-done'] button",
    "button:has-text('Yayınla')",
    "button:has-text('Publish')",
]

# Yayınlandığında beliren onay / pine gidiş bağlantısı.
BASARI_ISARETLERI = [
    "a[href*='/pin/']",
    "text=/Pin'iniz yayınlandı|Pin'in yayınlandı|Your Pin was published|Pin'iniz oluşturuldu/i",
    # Yayınlandıktan sonra editör kapanıp boş yükleme ekranına dönüyor.
    "[data-test-id='storyboard-draft-upload-container']",
]

# Pinterest bir şeyi beğenmediğinde çıkan hata kutuları.
HATA_ISARETLERI = [
    "div[role='alert']",
    "[data-test-id='storyboard-error']",
]
