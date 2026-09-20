// PttAVM siparisleri: Gmail'deki 'Yeni Siparisiniz Var' maillerinden acik siparisleri JSON dondurur.
// GET ?tip=pttavm[&gun=3]  -> [{no, tarih, urun, tutar}]  (varsayilan son 3 gun; kapali kontrolu yalniz KONUDA)
// GET ?tip=dbg[&gun=14]    -> ham mail metni (teshis)
// Dagitim: Web uygulamasi, "Ben" olarak, erisim "Herkes"; URL GitHub secret STOK_SHEET_WEBHOOK (tools/telegram_ozet.py).
// 20.09.2026 dagitildi (surum 10). Mail govdesinde numara *yildiz* icinde: "Siparis numarasi *PTT-...*".
function pttavmAcik(gun) {
  gun = parseInt(gun, 10) > 0 ? parseInt(gun, 10) : 3;
  var acik = {}, kapali = {};
  var threads = GmailApp.search('from:pttavm.com newer_than:' + gun + 'd', 0, 60);
  threads.forEach(function (t) {
    t.getMessages().forEach(function (m) {
      var s = m.getSubject() || '';
      var g = m.getPlainBody() + ' ' + s;
      var no = (g.match(/Sipari[şs]\s*(No|Numaras[ıi])[\s:#*]*([A-Z0-9-]{6,})/i) || [])[2];
      if (!no) return;
      if (/kargoya verildi|kargoland|teslim edildi|iptal|iade/i.test(s)) { kapali[no] = true; return; }
      if (/yeni sipari/i.test(s)) {
        var tutar = (g.match(/([\d.]+,\d{2})\s*(TL|₺)/) || [])[1] || '';
        var urun = (g.match(/Fiyat[\s\S]*?>\s*([^<>\n]{5,120}?)\s*<https/) || [])[1] || '';
        acik[no] = { no: no, tarih: m.getDate(), urun: String(urun).slice(0, 80), tutar: tutar };
      }
    });
  });
  return Object.keys(acik).filter(function (k) { return !kapali[k]; }).map(function (k) { return acik[k]; });
}

function pttavmDbg(gun) {
  gun = parseInt(gun, 10) > 0 ? parseInt(gun, 10) : 14;
  var out = [];
  GmailApp.search('from:pttavm.com newer_than:' + gun + 'd', 0, 20).forEach(function (t) {
    t.getMessages().forEach(function (m) { out.push({ konu: m.getSubject(), tarih: m.getDate(), govde: String(m.getPlainBody() || '').replace(/\s+/g, ' ').slice(0, 1500) }); });
  });
  return out;
}

function doGet(e) {
  var p = (e && e.parameter) || {};
  var out = p.tip === 'pttavm' ? pttavmAcik(p.gun) : p.tip === 'dbg' ? pttavmDbg(p.gun) : { ok: true };
  return ContentService.createTextOutput(JSON.stringify(out)).setMimeType(ContentService.MimeType.JSON);
}

function doPost(e) {
  return ContentService.createTextOutput('ok');
}
