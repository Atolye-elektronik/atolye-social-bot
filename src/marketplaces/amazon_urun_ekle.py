# -*- coding: utf-8 -*-
"""Amazon.com.tr'ye urun ekleme (SP-API Listings Items 2021-08-01).

Kaynak: content/n11_urunler.json (TY tabanli katalog: ad, aciklama, gorseller, tyFiyat, desi, stok).
Kurallar (kullanici, 08.09.2026):
  - Baslik en fazla 75 karakter, "Arduino" tek basina degil "Arduino Uyumlu".
  - Promosyon ifadesi yok (hediyeli, ucretsiz kargo...), HEPSI BUYUK yok.
  - Kargo musteriye ucretsiz + satici oder -> yalniz TY fiyati >= 400 TL olan urunler.
  - Barkodlarimiz GS1 degil -> supplier_declared_has_product_identifier_exemption=true ile barkodsuz.

    python src/marketplaces/amazon_urun_ekle.py --onizle            # VALIDATION_PREVIEW, hicbir sey yazmaz
    python src/marketplaces/amazon_urun_ekle.py --onizle --kod AETMRNDFTR10
    python src/marketplaces/amazon_urun_ekle.py --gonder --kod AETMRNDFTR10
    python src/marketplaces/amazon_urun_ekle.py --gonder             # hepsini bas
"""
import argparse
import html
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import amazon_client as az

KOK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KAYNAK = os.path.join(KOK, "content", "n11_urunler.json")
CIKTI = os.path.join(KOK, "content", "amazon_urunler.json")
MIN_FIYAT = 400.0
HARIC = {"AEUT12D", "AEARNANOTC"}   # UT12D yalniz Trendyol; Nano zaten AEMZNARNN001 olarak Amazon'da (B0H96QCN1N)
MARKA = "Atölye Elektronik"
JENERIK = False           # --jenerik: marka "Genel" (barkodsuz otomatik muafiyet); defterler haric
JENERIK_MARKA = os.environ.get("AMAZON_JENERIK_MARKA", "Genel")

# browse node'lar (catalog aramasindan, 09.09.2026)
NODE = {"defter": "12923445031", "bilim": "12923392031", "modul": "12707617031", "role": "12708550031",
        "motor": "51354639031", "kablo": "12707183031", "lehim": "12708352031", "aletkutu": "12707430031",
        "alettakim": "12707437031", "pense": "12708163031"}

# SKU -> (productType, node, mensei). Listede olmayan SKU varsayilana gider (kit/set).
OZEL = {
    "AETMRNDFTR10": ("BLANK_BOOK", "defter", "TR"), "AETMRNDFTR20": ("BLANK_BOOK", "defter", "TR"),
    "AETMRNDFTR30": ("BLANK_BOOK", "defter", "TR"), "AEISDSYS10": ("BLANK_BOOK", "defter", "TR"),
    "AEISDSYS20": ("BLANK_BOOK", "defter", "TR"),
    "AEARNANOTC2": ("SINGLE_BOARD_COMPUTER", "modul", "CN"), "AEARNANOTC": ("SINGLE_BOARD_COMPUTER", "modul", "CN"),
    "AEUNOR33": ("SINGLE_BOARD_COMPUTER", "modul", "CN"), "AEL298NMTRT": ("SINGLE_BOARD_COMPUTER", "modul", "CN"),
    "AE16X2LCD2": ("SINGLE_BOARD_COMPUTER", "modul", "CN"), "AERTC13025": ("SINGLE_BOARD_COMPUTER", "modul", "CN"),
    "AEHCSR045": ("SINGLE_BOARD_COMPUTER", "modul", "CN"), "AE6X13PLK5": ("SINGLE_BOARD_COMPUTER", "modul", "CN"),
    "AETKRM5V5": ("SINGLE_BOARD_COMPUTER", "modul", "CN"),   # RELAY tipi kategori onayi istiyor (09.09) -> modul
    "AESG905": ("SINGLE_BOARD_COMPUTER", "modul", "CN"), "AE3-6VMTR4": ("SINGLE_BOARD_COMPUTER", "modul", "CN"),  # ELECTRIC_MOTOR onay istiyor
    "AEJK2040EEDE33": ("SINGLE_BOARD_COMPUTER", "modul", "CN"), "AEJK2040222": ("SINGLE_BOARD_COMPUTER", "modul", "CN"),  # ELECTRONIC_WIRE onay istiyor
    "AEZD30C40W": ("SOLDERING_IRON", "lehim", "CN"), "AEHVYST6P": ("SOLDERING_IRON", "lehim", "CN"),
    "AETC162": ("PORTABLE_TOOL_BOX", "aletkutu", "CN"), "AETCS9P": ("PORTABLE_TOOL_BOX", "alettakim", "CN"),
    "AETCS18P": ("PORTABLE_TOOL_BOX", "alettakim", "CN"),
    "AEEAS3P": ("PLIERS", "pense", "CN"), "AEEAS7P": ("PLIERS", "pense", "CN"),
}
VARSAYILAN = ("SCIENCE_FUNDAMENTALS_KIT", "bilim", "TR")   # kitler / setler / robot arabalar

PROMO = re.compile(r"\b(hediyeli|hediye|ücretsiz kargo|ucretsiz kargo|kampanya|indirim|fırsat)\b", re.I)


def baslik(ad):
    t = html.unescape(ad)
    t = re.sub(r"\s*[|—–]\s*", " - ", t)
    t = PROMO.sub("", t)
    t = re.sub(r"\bArduino(?!\s+(Uyumlu|ile Uyumlu))", "Arduino Uyumlu", t)
    t = re.sub(r"\s+", " ", t).replace(" - -", " -").strip(" -")
    if len(t) > 75:  # ilk ayiracta kes, yine uzunsa kelime sinirinda kes
        parcalar = t.split(" - ")
        t2 = parcalar[0]
        for p in parcalar[1:]:
            if len(t2) + 3 + len(p) <= 75:
                t2 += " - " + p
        t = t2 if len(t2) <= 75 else t2[:75].rsplit(" ", 1)[0]
    return t.strip(" -,+(").rstrip(" +-(,")


def temiz_metin(s):
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"\s+", " ", s).strip()


def maddeler(aciklama, ad):
    m = [temiz_metin(x) for x in re.split(r";|\n|(?<=[.!])\s+(?=[A-ZÇĞİÖŞÜ])", aciklama or "")]
    m = [PROMO.sub("", x).strip() for x in m if 25 <= len(x) <= 250]
    if JENERIK:
        m = [re.sub(r"At[öo]lye Elektronik( taraf[ıi]ndan)?", "", x).strip() for x in m]
    out = []
    for x in m:
        if x not in out:
            out.append(x[:240])
        if len(out) == 5:
            break
    while len(out) < 3:
        out.append("%s - meslek lisesi, hobi ve eğitim projeleri için." % temiz_metin(ad)[:150])
    return out


def kur(u):
    sku = u["tyStokKodu"]
    pt, node, mensei = OZEL.get(sku) or VARSAYILAN
    mk = az.MARKET
    ad = baslik(u["ad"])
    acik = temiz_metin(u.get("aciklama") or "")
    if len(acik) < 60:
        acik = "%s. %s" % (ad, "Atölye Elektronik tarafından meslek liseleri, hobi elektroniği ve eğitim projeleri için hazırlanmıştır.")
    acik = PROMO.sub("", acik)[:1900]
    gorseller = [g for g in (u.get("gorseller") or []) if str(g).startswith("http")][:8]
    adet = int(float(u.get("stok") or 0))
    fiyat = float(u.get("tyFiyat") or 0)
    marka = JENERIK_MARKA if JENERIK else MARKA
    if JENERIK:
        acik = re.sub(r"At[öo]lye Elektronik( taraf[ıi]ndan)?", "", acik)
    A = {
        "item_name": [{"value": ad, "language_tag": "tr_TR", "marketplace_id": mk}],
        "brand": [{"value": marka, "language_tag": "tr_TR", "marketplace_id": mk}],
        "manufacturer": [{"value": marka, "language_tag": "tr_TR", "marketplace_id": mk}],
        "part_number": [{"value": sku, "marketplace_id": mk}],
        "model_number": [{"value": sku, "marketplace_id": mk}],
        "bullet_point": [{"value": b, "language_tag": "tr_TR", "marketplace_id": mk} for b in maddeler(u.get("aciklama"), u["ad"])],
        "product_description": [{"value": acik, "language_tag": "tr_TR", "marketplace_id": mk}],
        "country_of_origin": [{"value": mensei, "marketplace_id": mk}],
        "supplier_declared_dg_hz_regulation": [{"value": "not_applicable", "marketplace_id": mk}],
        "recommended_browse_nodes": [{"value": NODE[node], "marketplace_id": mk}],
        "supplier_declared_has_product_identifier_exemption": [{"value": True, "marketplace_id": mk}],
        "condition_type": [{"value": "new_new", "marketplace_id": mk}],
        "color": [{"value": "Çok Renkli", "language_tag": "tr_TR", "marketplace_id": mk}],
        "number_of_items": [{"value": 1, "marketplace_id": mk}],
        "item_package_quantity": [{"value": 1, "marketplace_id": mk}],
        "batteries_required": [{"value": False, "marketplace_id": mk}],
        "generic_keyword": [{"value": "meslek lisesi elektronik arduino uyumlu eğitim seti", "language_tag": "tr_TR", "marketplace_id": mk}],
        "fulfillment_availability": [{"fulfillment_channel_code": "DEFAULT", "quantity": adet}],
        "purchasable_offer": [{"marketplace_id": mk, "currency": "TRY", "our_price": [{"schedule": [{"value_with_tax": fiyat}]}]}],
    }
    if gorseller:
        A["main_product_image_locator"] = [{"media_location": gorseller[0], "marketplace_id": mk}]
        for i, g in enumerate(gorseller[1:8], 1):
            A["other_product_image_locator_%d" % i] = [{"media_location": g, "marketplace_id": mk}]
    if pt == "SCIENCE_FUNDAMENTALS_KIT":
        A["age_range_description"] = [{"value": "14 yaş ve üzeri", "language_tag": "tr_TR", "marketplace_id": mk}]
    ek_alanlar(A, pt, sku, u, mk)
    return sku, {"productType": pt, "requirements": "LISTING", "attributes": A}


# desi -> yaklasik kutu olcusu (cm); Amazon boyut istiyor, TY'de yalniz desi var
BOYUT = {1: (20, 15, 8), 2: (25, 20, 12), 3: (30, 22, 15), 4: (35, 25, 15), 5: (35, 28, 18), 6: (40, 30, 20),
         7: (40, 30, 25), 10: (45, 35, 25)}


def _boyut(desi):
    d = int(float(desi or 1)); d = min(BOYUT, key=lambda k: abs(k - d))
    L, W, H = BOYUT[d]
    return {"length": {"value": L, "unit": "centimeters"}, "width": {"value": W, "unit": "centimeters"},
            "height": {"value": H, "unit": "centimeters"}}


def ek_alanlar(A, pt, sku, u, mk):
    """Urun tipine gore Amazon'un zorunlu tuttugu ek alanlar (09.09.2026 VALIDATION_PREVIEW sonucu)."""
    ad = A["item_name"][0]["value"]
    tr = lambda v: [{"value": v, "language_tag": "tr_TR", "marketplace_id": mk}]
    dz = lambda v: [{"value": v, "marketplace_id": mk}]
    A["included_components"] = tr("Ürün açıklamasında listelenen tüm parçalar")
    A["warranty_description"] = tr("2 yıl üretici garantisi (6502 sayılı kanun)")
    A["model_name"] = tr(sku)
    A["unit_count"] = [{"value": 1, "type": {"value": "Adet", "language_tag": "tr_TR"}, "marketplace_id": mk}]
    A["material"] = tr("Plastik, Metal, Elektronik bileşen")
    A["power_plug_type"] = dz("no_plug")
    A["accepted_voltage_frequency"] = dz("220v_240v_50hz")
    A["item_dimensions"] = [dict(_boyut(u.get("desi")), marketplace_id=mk)]
    if pt == "SCIENCE_FUNDAMENTALS_KIT":
        A["is_assembly_required"] = dz(True)
        A["assembly_time"] = [{"value": 45, "unit": "minutes", "marketplace_id": mk}]
        A["target_audience_keyword"] = tr("Öğrenciler, Öğretmenler, Hobi elektronikçileri")
        A["safety_warning"] = tr("Küçük parçalar içerir. 14 yaş altı için uygun değildir; yetişkin gözetiminde kullanılmalıdır.")
        A["manufacturer_minimum_age"] = dz(168)
        A["eu_toys_safety_directive_language"] = dz("turkish")
        A["eu_toys_safety_directive_warning"] = dz("adult_supervision_required")
        A["eu_toys_safety_directive_age_warning"] = dz("no_warning_applicable")
    if pt == "PORTABLE_TOOL_BOX":
        A["item_length_width_height"] = [dict(_boyut(u.get("desi")), marketplace_id=mk)]
        A["material"] = tr("Plastik, Çelik")
    if pt == "PLIERS":
        A["material"] = tr("Çelik, Plastik sap")
    if pt == "SOLDERING_IRON":
        A["power_source_type"] = tr("Elektrikli (kablolu)")
        A["power_plug_type"] = dz("type_cef_2pin_eu")
    if pt == "RELAY":
        A["connector_type"] = tr("Vidalı terminal")
        A["contact"] = [{"type": [{"value": "SPDT", "language_tag": "tr_TR"}], "material": [{"value": "Gümüş alaşım", "language_tag": "tr_TR"}],
                         "current_rating": [{"value": 10, "unit": "amps"}], "marketplace_id": mk}]
        A["current_rating"] = [{"value": 10, "unit": "amps", "marketplace_id": mk}]
        A["input_voltage"] = [{"value": 5, "unit": "volts_of_direct_current", "marketplace_id": mk}]
        A["operating_voltage"] = [{"value": 5, "unit": "volts_of_direct_current", "marketplace_id": mk}]
        A["measurement_system"] = tr("Metrik")
        A["mounting_type"] = tr("PCB / Panel")
        A["specification_met"] = tr("CE")


def secilenler(kod=None):
    d = json.load(open(KAYNAK, encoding="utf-8"))
    out = [u for u in d if u.get("tyStokKodu") and u["tyStokKodu"] not in HARIC and float(u.get("tyFiyat") or 0) >= MIN_FIYAT]
    if JENERIK:  # markali (kapaginda adimiz basili) defterler jenerik girilemez
        out = [u for u in out if (OZEL.get(u["tyStokKodu"]) or VARSAYILAN)[0] != "BLANK_BOOK"]
    if kod:
        out = [u for u in out if u["tyStokKodu"] in kod]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--onizle", action="store_true")
    ap.add_argument("--gonder", action="store_true")
    ap.add_argument("--kod", nargs="*")
    ap.add_argument("--yaz", action="store_true", help="payloadlari content/amazon_urunler.json'a yaz")
    ap.add_argument("--jenerik", action="store_true", help="marka Genel ile (defterler haric)")
    a = ap.parse_args()
    global JENERIK
    JENERIK = a.jenerik
    urunler = secilenler(a.kod)
    print("urun:", len(urunler))
    hepsi, sonuc = {}, {}
    for u in urunler:
        sku, body = kur(u)
        hepsi[sku] = body
        if not (a.onizle or a.gonder):
            print(sku, "|", body["attributes"]["item_name"][0]["value"], "|", body["productType"])
            continue
        params = {"marketplaceIds": az.MARKET}
        if a.onizle and not a.gonder:
            params["mode"] = "VALIDATION_PREVIEW"
        r = az._req("PUT", "/listings/2021-08-01/items/%s/%s" % (az.SELLER, sku), params=params, json=body)
        try:
            j = r.json()
        except Exception:
            j = {"raw": r.text[:200]}
        iss = [(i.get("severity"), i.get("code"), (i.get("message") or "")[:110], i.get("attributeNames")) for i in j.get("issues", [])]
        err = [i for i in iss if i[0] == "ERROR"]
        sonuc[sku] = {"status": j.get("status"), "submissionId": j.get("submissionId"), "issues": iss}
        print("%-16s %s %s | hata %d uyari %d" % (sku, r.status_code, j.get("status"), len(err), len(iss) - len(err)))
        for i in err:
            print("      ", i[1], i[2], i[3])
        time.sleep(0.3)
    if a.yaz:
        json.dump(hepsi, open(CIKTI, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if sonuc:
        json.dump(sonuc, open(os.path.join(KOK, "content", "amazon_sonuc.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
