/**
 * PttAVM siparisleri -> Gmail'den yakala -> GET ile disari ver.
 * Kurulum (kullanici, Google hesabinda):
 *  1. Mevcut "stok sheet webhook" Apps Script projesini ac (STOK_SHEET_WEBHOOK'un projesi).
 *  2. Bu dosyanin icerigini yeni bir .gs dosyasi olarak yapistir.
 *  3. Tetikleyiciler > "pttavmTara" icin zaman tabanli tetikleyici ekle (her 15 dakikada).
 *  4. Dagit > Yeni surum (web uygulamasi, "Erisim: Herkes"). URL degismezse GitHub secret ayni kalir.
 * GitHub tarafinda tools/telegram_ozet.py, STOK_SHEET_WEBHOOK + "?tip=pttavm" adresinden JSON okur.
 */
var PTT_SHEET = "pttavm_siparis";

function pttavmTara() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(PTT_SHEET) || ss.insertSheet(PTT_SHEET);
  if (sh.getLastRow() === 0) sh.appendRow(["siparisNo", "tarih", "urun", "tutar", "mailId", "durum"]);
  var bilinen = {};
  sh.getDataRange().getValues().slice(1).forEach(function (r) { bilinen[r[4]] = true; });
  // PttAVM siparis maili: gonderen pttavm.com, konu "sipariş"
  var threads = GmailApp.search('from:pttavm.com (sipariş OR siparis) newer_than:14d', 0, 50);
  threads.forEach(function (t) {
    t.getMessages().forEach(function (m) {
      var id = m.getId();
      if (bilinen[id]) return;
      var g = m.getPlainBody();
      var no = (g.match(/Sipari[sş]\s*(No|Numaras[ıi])\s*[:#]?\s*([A-Z0-9-]{6,})/i) || [])[2] || "";
      var tutar = (g.match(/([\d.]+,\d{2})\s*(TL|₺)/) || [])[1] || "";
      var urun = (g.match(/Ürün\s*Ad[ıi]?\s*[:]\s*(.+)/i) || [])[1] || m.getSubject();
      var kargo = /kargoya verildi|kargolandı|teslim/i.test(g + m.getSubject()) ? "kargolandi" : "yeni";
      sh.appendRow([no, m.getDate(), String(urun).slice(0, 80), tutar, id, kargo]);
    });
  });
}

// Mevcut doGet varsa icine bu dali ekle:
function doGet(e) {
  if (e && e.parameter && e.parameter.tip === "pttavm") {
    var sh = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(PTT_SHEET);
    var rows = sh ? sh.getDataRange().getValues().slice(1) : [];
    var out = rows.filter(function (r) { return r[5] === "yeni"; }).map(function (r) {
      return { no: r[0], tarih: r[1], urun: r[2], tutar: r[3] };
    });
    return ContentService.createTextOutput(JSON.stringify(out)).setMimeType(ContentService.MimeType.JSON);
  }
  return ContentService.createTextOutput("ok");
}
