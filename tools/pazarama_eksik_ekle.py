# -*- coding: utf-8 -*-
"""Pazarama'da olmayan Trendyol urunlerini Pazarama'ya acar (12.09.2026).

Kategori: TY kategorisine gore Pazarama kategori GUID'i (KAT_ESLE).
Fiyat   : ORTAK-BARKOD-BUYBOX analizinde "girebiliriz" cikan urunlerde rakip-1 TL;
          digerlerinde TY ile esit net formulu (pazarama_yeni10.fiyat mantigi).
Icerik  : baslik/aciklama/gorsel/barkod/desi Trendyol urun kaydindan.

    python tools/pazarama_eksik_ekle.py            # kuru calisma (payload uretir)
    python tools/pazarama_eksik_ekle.py --uygula   # gonderir
    python tools/pazarama_eksik_ekle.py --sonuc <batchId>
"""
from __future__ import annotations
import argparse, base64, json, math, os, pathlib, re, sys

KOK = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))
sys.path.insert(0, str(KOK / "src"))
sys.path.insert(0, str(KOK / "src" / "marketplaces"))
import requests  # noqa: E402


def _env():
    for yol in (KOK / ".env", pathlib.Path("C:/Users/serdar/Desktop/atolyesocialbotmasaustu/.env")):
        if not yol.exists():
            continue
        for l in open(yol, encoding="utf-8"):
            m = re.match(r"([A-Z0-9_]+)=(.*)", l.strip())
            if m:
                os.environ.setdefault(m.group(1), m.group(2).strip().strip('"').strip("'"))


_env()
import pazarama_client as pz  # noqa: E402

SCRATCH = pathlib.Path("C:/Users/serdar/AppData/Local/Temp/claude/C--Users-serdar-Desktop-atolyesocialbotmasaustu/a4d0556e-5012-4f53-831e-17e87b486275/scratchpad/buybox")

# TY kategorisi -> (Pazarama kategori GUID, komisyon KDV haric)
KAT_ESLE = {
    "Elektronik Devre Elemanı": ("5fcd4444-87f0-4f3a-8ecf-3df2a91bd7b9", 0.14),
    "Robotik Malzeme":          ("5fcd4444-87f0-4f3a-8ecf-3df2a91bd7b9", 0.14),
    "Bilgisayar Yedek Parça":   ("5fcd4444-87f0-4f3a-8ecf-3df2a91bd7b9", 0.14),
    "Hobi Makineleri ve Aksesuarları": ("5fcd4444-87f0-4f3a-8ecf-3df2a91bd7b9", 0.14),
    "Pil & Şarj Cihazı":        ("5fcd4444-87f0-4f3a-8ecf-3df2a91bd7b9", 0.14),
    "RC Yedek Parça":           ("5fcd4444-87f0-4f3a-8ecf-3df2a91bd7b9", 0.14),
    "Defter":                   ("ac6c409f-f2f5-4a9b-8e15-d6ca0604b02b", 0.18),
    "Takım Çantası & Avadanlık": ("38210217-b841-4368-9f13-90f10482977e", 0.17),
    "Saklama Kutusu":           ("38210217-b841-4368-9f13-90f10482977e", 0.17),
    "Tornavida":                ("2997cdc1-84de-40a3-963f-20217f03f7de", 0.17),
    "Lehim & Havya":            ("d76b5570-d87e-4ae1-ba5f-8e444dc9365a", 0.17),
    "Akıllı Sensörler":         ("5fcd4444-87f0-4f3a-8ecf-3df2a91bd7b9", 0.14),
    "Eğitici Oyuncak":          ("5fcd4444-87f0-4f3a-8ecf-3df2a91bd7b9", 0.14),
    "El Aletleri Aksesuar Seti": ("38210217-b841-4368-9f13-90f10482977e", 0.17),
}
# kategori GUID -> zorunlu ozellik secimleri (ad -> deger)
ZORUNLU = {
    "ac6c409f-f2f5-4a9b-8e15-d6ca0604b02b": {"Ürün Türü": "Defter", "Renk": "Beyaz"},
    "38210217-b841-4368-9f13-90f10482977e": {"Ürün Türü": "Malzemeli", "Renk": "Siyah", "Kilit": "Var",
                                             "Çıkarılabilir Raf": "Yok", "Ürün Tipi": "Takım Çantası"},
    "2997cdc1-84de-40a3-963f-20217f03f7de": {"Renk": "Siyah"},
}
# eklenmeyecekler: TY'deki mukerrer / ortak barkod ilanlari ve yalniz-TY kurali
ATLA = {"AEARISES88", "AEARNANOTC2", "AEDHT11-BB", "AEHC06BT-BB", "AEJK2040222",
        "AETY4LUMTRST", "AEUNOR32", "AEUT12D"}


def ty_urunler() -> dict:
    sid = os.environ["TRENDYOL_SUPPLIER_ID"]
    auth = base64.b64encode(f"{os.environ['TRENDYOL_API_KEY']}:{os.environ['TRENDYOL_API_SECRET']}".encode()).decode()
    h = {"Authorization": "Basic " + auth, "User-Agent": f"{sid} - SelfIntegration"}
    r = requests.get(f"https://apigw.trendyol.com/integration/product/sellers/{sid}/products",
                     params={"page": 0, "size": 200, "approved": "true"}, headers=h, timeout=90)
    return {x["stockCode"]: x for x in r.json()["content"] if x.get("stockCode")}


def kargo_ty(t): return 54.58 if t < 200 else (85.41 if t < 350 else 95.54)
def kargo_pz(p): return 54.58 if p < 150 else (85.41 if p <= 300 else 97.98)


def esit_net_fiyat(p_ty, kom):
    """TY neti ile ayni neti veren en dusuk Pazarama fiyati."""
    ty_net = p_ty * (1 / 1.2 - 0.033) - kargo_ty(p_ty) - 11
    adaylar = []
    for k in (54.58, 85.41, 97.98):
        p = math.ceil((ty_net + k) / (1 / 1.2 - kom))
        if kargo_pz(p) == k:
            adaylar.append(p)
    return max(min(adaylar) if adaylar else math.ceil((ty_net + 85.41) / (1 / 1.2 - kom)), math.ceil(p_ty))


def temiz(ham: str) -> str:
    t = re.sub(r"<[^>]+>", " ", ham or "")
    t = t.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", '"')
    return re.sub(r"\s+", " ", t).strip()


def ozellik_kur(gid, ozl):
    d = ozl.get(gid) or {}
    secim = ZORUNLU.get(gid, {})
    out, eksik = [], []
    for a in d.get("attributes") or []:
        vals = a.get("attributeValues") or []
        istenen = secim.get(a.get("name"))
        v = None
        if istenen:
            v = next((x for x in vals if (x.get("value") or x.get("name")) == istenen), None)
        if v is None and a.get("isRequired") and vals:
            v = vals[0]
        if v is None and not a.get("isRequired") and vals and a.get("name") == "Renk":
            v = next((x for x in vals if (x.get("value") or x.get("name")) in ("Gri", "Siyah")), vals[0])
        if v:
            out.append({"attributeId": a["id"], "attributeValueId": v["id"]})
        elif a.get("isRequired"):
            eksik.append(a.get("name"))
    return out, eksik


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--uygula", action="store_true")
    ap.add_argument("--adet", type=int, default=0)
    ap.add_argument("--sonuc")
    a = ap.parse_args()
    _env()
    if a.sonuc:
        r = pz.get("/product/getProductBatchResult", batchRequestId=a.sonuc)
        print(r.status_code, r.text[:3000]); return 0

    eksik = json.load(open(SCRATCH / "eksik_urunler.json", encoding="utf-8"))["pz"]
    ozl = json.load(open(SCRATCH / "pz_kat_ozellik.json", encoding="utf-8"))
    rekabet = {x["sk"]: x for x in json.load(open(SCRATCH / "rekabet.json", encoding="utf-8"))
               if x["kanal"] == "Pazarama" and x["durum"] in ("GIREBILIRIZ - fiyat kir", "yokuz - girebiliriz")}
    ty = ty_urunler()
    from marketplaces.pazarama_urun_ekle import marka_id
    mid = marka_id()

    urunler, atlanan = [], []
    for e in eksik:
        sk = e["sk"]
        if sk in ATLA:
            atlanan.append((sk, "mukerrer/ortak barkod/yalniz-TY")); continue
        t = ty.get(sk)
        if not t:
            atlanan.append((sk, "TY kaydi yok")); continue
        kat = KAT_ESLE.get(t.get("categoryName"))
        if not kat:
            atlanan.append((sk, "kategori eslesmedi: " + str(t.get("categoryName")))); continue
        gid, kom = kat
        gorseller = [g.get("url") for g in (t.get("images") or []) if g.get("url")][:8]
        if not gorseller:
            atlanan.append((sk, "gorsel yok")); continue
        p_ty = float(t.get("salePrice") or 0)
        hedef = rekabet.get(sk)
        if hedef and hedef.get("hedef_fiyat"):
            p = float(hedef["hedef_fiyat"]); kaynak = "rakip-1"
        else:
            p = float(esit_net_fiyat(p_ty, kom)); kaynak = "esit-net"
        attrs, eks = ozellik_kur(gid, ozl)
        if eks:
            atlanan.append((sk, "zorunlu ozellik yok: " + ",".join(eks))); continue
        urunler.append({
            "name": str(t.get("title"))[:150], "displayName": str(t.get("title"))[:150],
            "description": temiz(t.get("description"))[:5000] or str(t.get("title")),
            "brandId": mid, "categoryId": gid,
            "code": str(t.get("barcode")), "stockCode": sk, "groupCode": sk, "barcode": str(t.get("barcode")),
            "listPrice": round(p, 2), "salePrice": round(p, 2), "vatRate": int(t.get("vatRate") or 20),
            "stockCount": int(t.get("quantity") or 0), "desi": int(t.get("dimensionalWeight") or 1),
            "images": [{"imageurl": g} for g in gorseller],
            "attributes": attrs,
        })
        print(f"  {sk:16s} TY {p_ty:>8.0f} -> PZ {p:>8.2f} ({kaynak:8s}) stok {t.get('quantity'):>3} {str(t.get('categoryName'))[:24]}")
    print(f"\nhazir: {len(urunler)} | atlanan: {len(atlanan)}")
    for sk, n in atlanan:
        print(f"   - {sk:16s} {n}")
    json.dump(urunler, open(KOK / "content" / "pazarama_eksik.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if not a.uygula:
        print("\n--- KURU CALISMA --- gondermek icin --uygula")
        return 0
    sec = urunler[: a.adet] if a.adet else urunler
    # Pazarama tek hatali urunde tum partiyi reddediyor -> teker teker gonder
    ok, hata = [], []
    for u in sec:
        r = pz.post("/product/create", {"products": [u]})
        try:
            j = r.json()
        except Exception:
            j = {}
        hatalar = ((j.get("data") or {}).get("error") or {}).get("errors") or []
        bid = (j.get("data") or {}).get("batchRequestId")
        if hatalar:
            hata.append((u["stockCode"], "; ".join(map(str, hatalar))[:110]))
            print(f"  X {u['stockCode']:16s} {'; '.join(map(str, hatalar))[:90]}")
        else:
            ok.append((u["stockCode"], bid))
            print(f"  + {u['stockCode']:16s} {u['salePrice']:>8} TL  batch {bid}")
    print(f"acilan: {len(ok)} | hatali: {len(hata)}")
    json.dump({"ok": ok, "hata": hata}, open(KOK / "content" / "pazarama_eksik_sonuc.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
