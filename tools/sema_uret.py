# -*- coding: utf-8 -*-
"""Set bağlantı şemaları: SVG üretir, Playwright ile PNG (web) + A4 yatay PDF (kargo) yazar.

Kullanım:  python tools/sema_uret.py [sema-adi ...]
Çıktı:     posts/media/sema/<ad>.svg / .jpg / .pdf
Stil: IR kumandalı robot şeması (kullanıcının referansı) ile aynı dil.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "posts" / "media" / "sema"
OUT.mkdir(parents=True, exist_ok=True)

W, H = 1600, 1000
RENK = {
    "bg": "#f7f9fc", "baslik": "#14213d", "marka": "#c8102e", "gri": "#5c6672",
    "teal": "#1a9e9a", "kirmizi": "#c62828", "lacivert": "#1f2a44", "koyu": "#2b2f36",
    "sari": "#fff3c4", "sari_k": "#e0b100",
    "red": "#e53935", "blk": "#1a1a1a", "org": "#f39c35", "grn": "#2e9e8f", "blu": "#3b6fc4",
    "pur": "#8e5ad4", "ylw": "#d8a800", "cyan": "#0aa6c9",
}


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class Sema:
    def __init__(self, baslik, altbaslik, model, notlar):
        self.baslik, self.altbaslik, self.model, self.notlar = baslik, altbaslik, model, notlar
        self.parts = []
        self.pins = {}  # (comp, pin) -> (x, y, side)

    # --- bileşenler -------------------------------------------------------
    def kutu(self, ad, x, y, w, h, renk, baslik, alt="", pins=(), r=14, yazi="#fff", alt_renk="#cfd8e3", font=30, hiza="orta"):
        """pins: (isim, taraf, oran) taraf: l/r/t/b ; oran 0-1 boyunca konum"""
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{renk}"/>')
        cy = y + h / 2
        tx, ta = (x + w / 2, "middle") if hiza == "orta" else ((x + w - 18, "end") if hiza == "sag" else (x + 18, "start"))
        self.parts.append(f'<text x="{tx}" y="{cy - (8 if alt else -10)}" text-anchor="{ta}" font-size="{font}" font-weight="700" fill="{yazi}">{esc(baslik)}</text>')
        if alt:
            self.parts.append(f'<text x="{tx}" y="{cy + 24}" text-anchor="{ta}" font-size="20" fill="{alt_renk}">{esc(alt)}</text>')
        for isim, taraf, oran in pins:
            if taraf == "l":
                px, py = x, y + h * oran
                self.parts.append(f'<text x="{x + 14}" y="{py + 7}" font-size="21" font-weight="700" fill="{yazi}">{esc(isim)}</text>')
            elif taraf == "r":
                px, py = x + w, y + h * oran
                self.parts.append(f'<text x="{x + w - 14}" y="{py + 7}" text-anchor="end" font-size="21" font-weight="700" fill="{yazi}">{esc(isim)}</text>')
            elif taraf == "t":
                px, py = x + w * oran, y
                self.parts.append(f'<text x="{px}" y="{y - 10}" text-anchor="middle" font-size="20" font-weight="700" fill="{RENK["baslik"]}">{esc(isim)}</text>')
            else:
                px, py = x + w * oran, y + h
                self.parts.append(f'<text x="{px}" y="{y + h + 26}" text-anchor="middle" font-size="20" font-weight="700" fill="{RENK["baslik"]}">{esc(isim)}</text>')
            self.pins[(ad, isim)] = (px, py, taraf)
            self.parts.append(f'<circle cx="{px}" cy="{py}" r="5" fill="#fff" stroke="{RENK["baslik"]}" stroke-width="2"/>')

    def motor(self, ad, x, y, etiket, alt):
        self.kutu(ad, x, y, 180, 100, RENK["lacivert"], etiket, alt, pins=(("", "l", 0.35), (" ", "l", 0.65)), font=24)
        self.parts.append(f'<circle cx="{x + 235}" cy="{y + 50}" r="36" fill="#2b2f36"/><circle cx="{x + 235}" cy="{y + 50}" r="12" fill="#f39c35"/>')

    def pil(self, ad, x, y, w, h, etiket, hucre=("18650", "18650"), alt=""):
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{RENK["koyu"]}"/>')
        n = len(hucre)
        for i, hh in enumerate(hucre):
            yy = y + 16 + i * ((h - 32) / n)
            self.parts.append(f'<rect x="{x + 22}" y="{yy + 4}" width="{w - 44}" height="{(h - 32) / n - 10}" rx="8" fill="#3d7a4a"/>')
            self.parts.append(f'<text x="{x + w / 2}" y="{yy + (h - 32) / n / 2 + 6}" text-anchor="middle" font-size="18" font-weight="700" fill="#fff">{esc(hh)}</text>')
        self.parts.append(f'<text x="{x + 36}" y="{y - 8}" font-size="22" font-weight="700" fill="{RENK["red"]}">+</text>')
        self.parts.append(f'<text x="{x + w - 36}" y="{y + h + 24}" font-size="22" font-weight="700" fill="{RENK["blk"]}">−</text>')
        self.parts.append(f'<text x="{x + w / 2}" y="{y + h + 30}" text-anchor="middle" font-size="20" font-weight="700" fill="{RENK["baslik"]}">{esc(etiket)}</text>')
        if alt:
            self.parts.append(f'<text x="{x + w / 2}" y="{y + h + 54}" text-anchor="middle" font-size="17" fill="{RENK["gri"]}">{esc(alt)}</text>')
        self.pins[(ad, "+")] = (x + 36, y, "t")
        self.pins[(ad, "-")] = (x + w - 36, y + h, "b")

    def etiket(self, x, y, metin, w=None):
        w = w or 18 + len(metin) * 11
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="30" rx="6" fill="{RENK["sari"]}" stroke="{RENK["sari_k"]}" stroke-width="2"/>'
                          f'<text x="{x + w / 2}" y="{y + 21}" text-anchor="middle" font-size="17" font-weight="700" fill="#5a4a00">{esc(metin)}</text>')

    def yazi(self, x, y, metin, renk="#5c6672", boyut=18, kalin=False, anchor="start"):
        self.parts.append(f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{boyut}" font-weight="{700 if kalin else 500}" fill="{renk}">{esc(metin)}</text>')

    # --- kablolar ----------------------------------------------------------
    def tel(self, renk, noktalar, w=5):
        d = " ".join(f"{'M' if i == 0 else 'L'} {x} {y}" for i, (x, y) in enumerate(noktalar))
        self.parts.append(f'<path d="{d}" fill="none" stroke="{RENK.get(renk, renk)}" stroke-width="{w}" stroke-linejoin="round" stroke-linecap="round"/>')

    def bagla(self, renk, a, b, via=None, w=5):
        """a,b: (comp,pin). via: ara noktalar listesi [(x,y)...] ya da None (L-biçimi)"""
        ax, ay, at = self.pins[a]
        bx, by, bt = self.pins[b]
        if via is None:
            mx = (ax + bx) / 2
            via = [(mx, ay), (mx, by)]
        self.tel(renk, [(ax, ay)] + list(via) + [(bx, by)], w)
        for x, y in ((ax, ay), (bx, by)):
            self.parts.append(f'<circle cx="{x}" cy="{y}" r="6" fill="{RENK.get(renk, renk)}"/>')

    def dugum(self, x, y, renk):
        self.parts.append(f'<circle cx="{x}" cy="{y}" r="7" fill="{RENK.get(renk, renk)}"/>')

    # --- çıktı --------------------------------------------------------------
    def svg(self):
        import textwrap
        satirlar = []
        for n in self.notlar:
            par = textwrap.wrap(n, 52)
            satirlar.append("• " + par[0]); satirlar += ["   " + x for x in par[1:]]
        notlar = "".join(
            f'<text x="1110" y="{742 + i * 25}" font-size="16.5" fill="#14213d">{esc(n)}</text>' for i, n in enumerate(satirlar))
        nh = 52 + 25 * len(satirlar)
        return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Segoe UI, Arial, sans-serif">
<defs><pattern id="dots" width="20" height="20" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1.3" fill="#d6dde8"/></pattern></defs>
<rect width="{W}" height="{H}" fill="{RENK["bg"]}"/><rect width="{W}" height="{H}" fill="url(#dots)"/>
<text x="50" y="58" font-size="40" font-weight="800" fill="{RENK["baslik"]}">{esc(self.baslik)} — Bağlantı Şeması</text>
<text x="50" y="92" font-size="21" fill="{RENK["gri"]}">{esc(self.altbaslik)}</text>
<text x="{W - 50}" y="52" text-anchor="end" font-size="22" font-weight="800" fill="{RENK["marka"]}">ATÖLYE ELEKTRONİK</text>
<text x="{W - 50}" y="84" text-anchor="end" font-size="18" fill="{RENK["gri"]}">Model: {esc(self.model)} · atolyeelektronik.com</text>
{"".join(self.parts)}
<rect x="1090" y="680" width="490" height="{nh}" rx="12" fill="#fff" stroke="#cfd8e3"/>
<rect x="1090" y="680" width="490" height="42" rx="12" fill="{RENK["baslik"]}"/><rect x="1090" y="700" width="490" height="22" fill="{RENK["baslik"]}"/>
<text x="1108" y="709" font-size="22" font-weight="700" fill="#fff">Önemli Notlar</text>
{notlar}
</svg>'''


# ============================ ŞEMALAR =====================================
def arduino(s, x=250, y=280, pins_r=(), pins_l=(), pins_t=(("5V", 0.3), ("VIN", 0.52)), pins_b=(("GND", 0.5),)):
    p = [(n, "r", o) for n, o in pins_r] + [(n, "l", o) for n, o in pins_l] + [(n, "t", o) for n, o in pins_t] + [(n, "b", o) for n, o in pins_b]
    s.kutu("ard", x, y, 300, 380, RENK["teal"], "Arduino", "UNO R3", pins=p, font=34, alt_renk="#ffffff")
    s.parts.append(f'<rect x="{x + 20}" y="{y + 20}" width="56" height="40" rx="6" fill="#cfd8e3"/>')


def l298n(s, x=760, y=270, ins=("IN1", "IN2", "IN3", "IN4")):
    pins = [("ENA", "l", 0.13)] + [(n, "l", 0.28 + i * 0.13) for i, n in enumerate(ins)] + [("ENB", "l", 0.82),
            ("OUT1", "r", 0.12), ("OUT2", "r", 0.24), ("OUT3", "r", 0.62), ("OUT4", "r", 0.74),
            ("+12V", "b", 0.18), ("GND", "b", 0.5), ("+5V", "b", 0.82)]
    s.kutu("l298", x, y, 280, 320, RENK["kirmizi"], "L298N", "Motor Sürücü", pins=pins, font=30, alt_renk="#ffd5d5")
    s.parts.append(f'<rect x="{x + 105}" y="{y + 50}" width="80" height="70" rx="8" fill="#2b2f36"/><text x="{x + 145}" y="{y + 92}" text-anchor="middle" font-size="14" fill="#fff">L298</text>')
    s.parts.append(f'<rect x="{x + 20}" y="{y + 300}" width="240" height="22" rx="4" fill="#2e7d32"/>')
    s.etiket(x - 190, y + 28, "JUMPER TAKILI", 170)
    s.etiket(x - 190, y + 248, "JUMPER TAKILI", 170)
    s.etiket(x + 300, y + 280, "5V jumper takılı olmalı", 200)
    s.yazi(x + 230, y + 352, "(kullanılmıyor)", boyut=15, anchor="middle")


def motorlar(s, x=1190):
    s.motor("mA", x, 280, "SOL MOTOR", "(Motor A)")
    s.motor("mB", x, 440, "SAĞ MOTOR", "(Motor B)")


def robot_govde(s, ek_l=()):
    """IR/BT/engel ortak iskelet: Arduino + L298N + motorlar + pil"""
    arduino(s, pins_r=(("D5", 0.2), ("D6", 0.31), ("D9", 0.42), ("D10", 0.53)) + tuple(ek_l))
    l298n(s)
    motorlar(s)
    s.pil("pil", 540, 760, 280, 110, "18650 Pil Yuvası (2'li seri) = 7.4V", alt="AA'lı sette: 4xAA = 6V")
    for i, (pin, inn, renk) in enumerate((("D5", "IN1", "org"), ("D6", "IN2", "grn"), ("D9", "IN3", "blu"), ("D10", "IN4", "pur"))):
        s.bagla(renk, ("ard", pin), ("l298", inn), via=[])
    # motorlar
    s.bagla("red", ("l298", "OUT1"), ("mA", ""), via=[]); s.bagla("blk", ("l298", "OUT2"), ("mA", " "), via=[])
    s.bagla("red", ("l298", "OUT3"), ("mB", ""), via=[]); s.bagla("blk", ("l298", "OUT4"), ("mB", " "), via=[])
    # güç
    px, py, _ = s.pins[("pil", "+")]
    s.tel("red", [(px, py), (px, 720), (810, 720), (810, 590)]); s.dugum(810, 590, "red")
    s.tel("red", [(810, 720), (1585, 720), (1585, 130), (406, 130), (406, 280)], w=5); s.dugum(406, 280, "red")
    s.yazi(900, 112, "Pil + (7.4V) → Arduino VIN", RENK["red"], 19, True, "middle")
    nx, ny, _ = s.pins[("pil", "-")]
    s.tel("blk", [(nx, ny), (nx, 905), (100, 905)]); s.tel("blk", [(nx, 905), (900, 905), (900, 590)]); s.dugum(900, 590, "blk")
    s.tel("blk", [(400, 660), (400, 905)]); s.dugum(400, 905, "blk"); s.dugum(900, 905, "blk")
    s.yazi(60, 913, "GND", RENK["baslik"], 22, True); s.yazi(850, 945, "ORTAK GND HATTI", RENK["baslik"], 19, True, "middle")


def sema_bt():
    s = Sema("Bluetooth Kontrollü Robot Araba Kiti", "2WD Şasi + Arduino UNO + L298N + HC-06 Bluetooth + 18650 Pil Yuvası (7.4V) — blogdaki hazır kodla birebir uyumludur", "AEHC06RAK-LI",
             ["Kod pinleri: IN1→D5, IN2→D6, IN3→D9, IN4→D10; HC-06 TXD→D0 (RX), RXD→D1 (TX).",
              "KOD YÜKLERKEN HC-06'nın TX/RX kablolarını çıkarın (USB ile çakışır).",
              "HC-06 RXD 3.3V'tur: D1→RXD hattına 1kΩ + 2kΩ gerilim bölücü önerilir.",
              "Arduino pilden VIN ile beslenir (7.4V); 5V pinine güç verilmez.",
              "ENA, ENB ve L298N 5V jumper'ları takılı kalmalı; GND'ler ortak olmalı.",
              "Telefonda 'Arduino Bluetooth Controller' ile F/B/L/R/S komutları gönderin.",
              "Eşleştirme şifresi genelde 1234."])
    robot_govde(s, ek_l=())
    s.kutu("bt", 40, 300, 170, 150, RENK["lacivert"], "", "", pins=(("VCC", "t", 0.5), ("GND", "b", 0.5), ("TXD", "r", 0.6), ("RXD", "r", 0.82)), font=26)
    s.yazi(125, 335, "HC-06", "#fff", 26, True, "middle"); s.yazi(125, 360, "Bluetooth", "#cfd8e3", 18, anchor="middle")
    # ekstra arduino pinleri
    s.pins[("ard", "D0")] = (250, 280 + 380 * 0.72, "l"); s.parts.append('<text x="264" y="560" font-size="21" font-weight="700" fill="#fff">D0 RX</text>'); s.parts.append('<circle cx="250" cy="553.6" r="5" fill="#fff" stroke="#14213d" stroke-width="2"/>')
    s.pins[("ard", "D1")] = (250, 280 + 380 * 0.85, "l"); s.parts.append('<text x="264" y="610" font-size="21" font-weight="700" fill="#fff">D1 TX</text>'); s.parts.append('<circle cx="250" cy="603" r="5" fill="#fff" stroke="#14213d" stroke-width="2"/>')
    s.bagla("ylw", ("bt", "TXD"), ("ard", "D0"), via=[(230, 390), (230, 553.6)])
    s.bagla("cyan", ("bt", "RXD"), ("ard", "D1"), via=[(222, 423), (222, 603)])
    s.etiket(150, 470, "1kΩ+2kΩ bölücü", 150)
    # 5V
    s.tel("red", [(125, 300), (125, 170), (340, 170), (340, 280)]); s.dugum(340, 280, "red"); s.dugum(125, 300, "red")
    s.yazi(60, 150, "+5V", RENK["red"], 22, True); s.yazi(380, 176, "Arduino 5V çıkışı → HC-06 VCC", RENK["red"], 17)
    s.tel("blk", [(125, 450), (125, 905)]); s.dugum(125, 450, "blk")
    return s


def sema_engel():
    s = Sema("Engelden Kaçan Robot Araba Kiti", "2WD Şasi + Arduino UNO + L298N + HC-SR04 Ultrasonik + SG90 Servo + 18650 Pil Yuvası — blogdaki kodla uyumludur", "AE2WDEKRBT-LI",
             ["Kod pinleri: IN1→D5, IN2→D6, IN3→D9, IN4→D10; TRIG→A0, ECHO→A1; Servo→D3.",
              "HC-SR04 ve servo Arduino 5V çıkışından beslenir; GND ortak.",
              "Servo sinyal kablosu (turuncu) D3'e, kırmızı 5V'a, kahverengi GND'ye.",
              "Arduino pilden VIN ile beslenir (7.4V). 5V pinine güç verilmez.",
              "ENA, ENB ve L298N 5V jumper'ları takılı kalmalı.",
              "Kod yüklerken pil şalterini kapatın; motor ters dönerse OUT uçlarını değiştirin."])
    robot_govde(s)
    s.kutu("sr", 30, 290, 190, 140, RENK["lacivert"], "HC-SR04", "Ultrasonik", pins=(("VCC", "t", 0.25), ("TRIG", "r", 0.45), ("ECHO", "r", 0.7), ("GND", "t", 0.75)), font=22, hiza="sol")
    s.kutu("sv", 30, 520, 190, 120, RENK["lacivert"], "SG90", "Servo", pins=(("SIG", "r", 0.3), ("5V", "r", 0.55), ("GND", "r", 0.8)), font=24, hiza="sol")
    for n, o in (("A0", 0.62), ("A1", 0.72), ("D3", 0.85)):
        s.pins[("ard", n)] = (250, 280 + 380 * o, "l"); s.parts.append(f'<text x="264" y="{280 + 380 * o + 7}" font-size="21" font-weight="700" fill="#fff">{n}</text>'); s.parts.append(f'<circle cx="250" cy="{280 + 380 * o}" r="5" fill="#fff" stroke="#14213d" stroke-width="2"/>')
    s.bagla("ylw", ("sr", "TRIG"), ("ard", "A0"), via=[(234, 353), (234, 515.6)])
    s.bagla("cyan", ("sr", "ECHO"), ("ard", "A1"), via=[(226, 388), (226, 553.6)])
    s.bagla("org", ("sv", "SIG"), ("ard", "D3"), via=[(238, 556), (238, 603)])
    s.tel("red", [(77, 290), (77, 170), (340, 170), (340, 280)]); s.dugum(340, 280, "red"); s.dugum(77, 290, "red")
    s.tel("red", [(220, 586), (242, 586), (242, 170)]); s.dugum(242, 170, "red")
    s.yazi(40, 150, "+5V", RENK["red"], 22, True); s.yazi(380, 176, "Arduino 5V çıkışı → sensör ve servo beslemesi", RENK["red"], 17)
    s.tel("blk", [(172, 290), (172, 230), (15, 230), (15, 905), (100, 905)]); s.dugum(172, 290, "blk")
    s.tel("blk", [(220, 616), (230, 616), (230, 905)]); s.dugum(230, 905, "blk")
    return s


def sema_3u1():
    s = Sema("3'ü 1 Arada Robot Araba Kiti", "Bluetooth + IR Kumanda + Engelden Kaçan — tek şasi, tek kod; mod kumandadan veya telefondan seçilir", "AE3IN1ROBOT-LI",
             ["L298N: IN1→D5, IN2→D6, IN3→D9, IN4→D10 (ENA/ENB jumper takılı).",
              "HC-06: TXD→D0, RXD→D1 (kod yüklerken çıkarın). IR alıcı OUT→D11.",
              "HC-SR04: TRIG→A0, ECHO→A1. SG90 servo sinyal→D3.",
              "Tüm modüller Arduino 5V çıkışından beslenir; Arduino VIN pilden (7.4V).",
              "Tüm GND'ler ortak olmalı. Kod yüklerken pil şalteri kapalı.",
              "Blogdaki 3'ü 1 arada kod: IR tuşuyla ya da telefondan 'A' ile otonom mod."])
    robot_govde(s)
    s.kutu("sr", 40, 230, 170, 110, RENK["lacivert"], "HC-SR04", "TRIG A0 · ECHO A1", pins=(("", "r", 0.4), (" ", "r", 0.7)), font=22)
    s.kutu("bt", 40, 370, 170, 110, RENK["lacivert"], "HC-06", "TXD D0 · RXD D1", pins=(("", "r", 0.4), (" ", "r", 0.7)), font=22)
    s.kutu("ir", 40, 510, 170, 100, RENK["lacivert"], "IR ALICI", "OUT D11", pins=(("", "r", 0.5),), font=22)
    s.kutu("sv", 40, 640, 170, 90, RENK["lacivert"], "SG90 Servo", "SIG D3", pins=(("", "r", 0.5),), font=22)
    for n, o in (("A0", 0.62), ("A1", 0.69), ("D0", 0.76), ("D1", 0.83), ("D11", 0.9), ("D3", 0.97)):
        y = 280 + 380 * o
        s.pins[("ard", n)] = (250, y, "l"); s.parts.append(f'<text x="264" y="{y + 7}" font-size="19" font-weight="700" fill="#fff">{n}</text>'); s.parts.append(f'<circle cx="250" cy="{y}" r="5" fill="#fff" stroke="#14213d" stroke-width="2"/>')
    s.bagla("ylw", ("sr", ""), ("ard", "A0"), via=[(226, 274), (226, 515.6)])
    s.bagla("cyan", ("sr", " "), ("ard", "A1"), via=[(232, 307), (232, 542.2)])
    s.bagla("grn", ("bt", ""), ("ard", "D0"), via=[(238, 414), (238, 568.8)])
    s.bagla("blu", ("bt", " "), ("ard", "D1"), via=[(244, 447), (244, 595.4)])
    s.bagla("org", ("ir", ""), ("ard", "D11"), via=[(222, 560), (222, 622)])
    s.bagla("pur", ("sv", ""), ("ard", "D3"), via=[(216, 685), (216, 648.6)])
    s.tel("red", [(125, 230), (125, 170), (340, 170), (340, 280)]); s.dugum(340, 280, "red")
    s.yazi(40, 150, "+5V (tüm modüller)", RENK["red"], 20, True)
    s.tel("blk", [(20, 905), (100, 905)]); s.yazi(40, 770, "GND: tüm modüllerin GND'si ortak hatta", RENK["gri"], 16)
    return s


def proje_kiti(baslik, alt, model, notlar, moduller, teller):
    """Arduino (solda) + modüller (sağda). moduller: [(ad, baslik, alt, y, pins[(isim,oran)])]; teller: [(renk, (ard_pin, oran_ard), (mod, pin))]"""
    s = Sema(baslik, alt, model, notlar)
    pins_r = tuple((p, o) for p, o in {t[1] for t in teller})
    arduino(s, x=200, y=260, pins_r=pins_r, pins_t=(("5V", 0.3), ("3.3V", 0.52)), pins_b=(("GND", 0.5),))
    for ad, bas, altm, y, pins in moduller:
        s.kutu(ad, 780, y, 300, 40 + 36 * len(pins), RENK["lacivert"], bas, altm, pins=tuple((p, "l", (i + 1) / (len(pins) + 1)) for i, p in enumerate(pins)), font=26, hiza="sag")
    for i, (renk, (ap, _), (m, mp)) in enumerate(teller):
        s.bagla(renk, ("ard", ap), (m, mp), via=[(540 + i * 24, s.pins[("ard", ap)][1]), (540 + i * 24, s.pins[(m, mp)][1])])
    return s


def sema_dht():
    s = proje_kiti("Sıcaklık-Nem İzleme Ekran Kiti", "Arduino UNO + DHT11 + 16x2 LCD (I2C) — blogdaki kodla birebir uyumludur", "AEDHTLCDSET",
                   ["DHT11 DATA→D7; LCD SDA→A4, SCL→A5 (I2C).", "DHT11 ve LCD 5V'tan beslenir; GND ortak.", "LCD adresi 0x27 değilse 0x3F deneyin (I2C tarama kodu).",
                    "Kütüphaneler: DHT sensor library (Adafruit), LiquidCrystal I2C.", "Ekran boşsa arka yüzdeki kontrast potunu çevirin."],
                   [("dht", "DHT11", "Sıcaklık-Nem", 280, ["VCC", "DATA", "GND"]), ("lcd", "16x2 LCD", "I2C Modüllü", 520, ["GND", "VCC", "SDA", "SCL"])],
                   [("org", ("D7", 0.35), ("dht", "DATA")), ("blu", ("A4", 0.6), ("lcd", "SDA")), ("grn", ("A5", 0.7), ("lcd", "SCL"))])
    guc_hatti(s, [("dht", "VCC"), ("lcd", "VCC")], [("dht", "GND"), ("lcd", "GND")])
    return s


def sema_rtc():
    s = proje_kiti("Dijital Saat & Takvim Projesi Kiti", "Arduino UNO + DS1302 RTC + 16x2 LCD (I2C) — blogdaki kodla birebir uyumludur", "AERTCLCDSET",
                   ["DS1302: DAT→D4, CLK→D5, RST→D2 (ThreeWire(4,5,2)).", "LCD SDA→A4, SCL→A5. Modüller 5V'tan beslenir; GND ortak.",
                    "Kütüphaneler: Rtc by Makuna, LiquidCrystal I2C.", "İlk yüklemede kod bilgisayar saatini RTC'ye aktarır.", "RTC üzerindeki CR2032 pil takılı olmalı."],
                   [("rtc", "DS1302", "RTC Modülü", 270, ["VCC", "GND", "CLK", "DAT", "RST"]), ("lcd", "16x2 LCD", "I2C Modüllü", 560, ["GND", "VCC", "SDA", "SCL"])],
                   [("pur", ("D2", 0.25), ("rtc", "RST")), ("org", ("D4", 0.35), ("rtc", "DAT")), ("ylw", ("D5", 0.45), ("rtc", "CLK")), ("blu", ("A4", 0.65), ("lcd", "SDA")), ("grn", ("A5", 0.75), ("lcd", "SCL"))])
    guc_hatti(s, [("rtc", "VCC"), ("lcd", "VCC")], [("rtc", "GND"), ("lcd", "GND")])
    return s


def sema_alarm():
    s = proje_kiti("Hareket Algılayan Sesli Alarm Kiti", "Arduino UNO + HC-SR501 PIR + Röle + Buzzer — blogdaki kodla birebir uyumludur", "AEPIRALARMSET",
                   ["PIR OUT→D7, Röle IN→D8, Buzzer (+)→D9.", "PIR, röle ve buzzer 5V'tan beslenir; GND ortak.", "PIR ilk açılışta ~30 sn ısınır; kod bunu bekler.",
                    "PIR üzerindeki potlar: hassasiyet ve gecikme süresi.", "Röle çıkışına (COM/NO) 220V bağlarken yetişkin gözetimi şart."],
                   [("pir", "HC-SR501", "PIR Hareket Sensörü", 270, ["VCC", "OUT", "GND"]), ("rol", "Röle Modülü", "Tek Kanal 5V", 470, ["VCC", "IN", "GND"]), ("buz", "Buzzer", "5V Aktif", 660, ["+", "−"])],
                   [("org", ("D7", 0.3), ("pir", "OUT")), ("blu", ("D8", 0.42), ("rol", "IN")), ("grn", ("D9", 0.54), ("buz", "+"))])
    guc_hatti(s, [("pir", "VCC"), ("rol", "VCC")], [("pir", "GND"), ("rol", "GND"), ("buz", "−")])
    return s


def sema_rfid():
    s = proje_kiti("RFID Kartlı Akıllı Kilit Kiti", "Arduino UNO + RC522 RFID + SG90 Servo — blogdaki kodla birebir uyumludur", "AERFIDKILITSET",
                   ["RC522: SDA(SS)→D10, SCK→D13, MOSI→D11, MISO→D12, RST→D9.", "RC522 3.3V ile beslenir (5V'a bağlamayın!). GND ortak.",
                    "Servo sinyal→D6, kırmızı→5V, kahverengi→GND.", "Kütüphaneler: MFRC522, Servo. Kart UID'sini Seri Monitör'den okuyup koda yazın.", "IRQ pini boş kalır."],
                   [("rc", "RC522", "RFID Okuyucu 13,56 MHz", 250, ["3.3V", "RST", "GND", "MISO", "MOSI", "SCK", "SDA"]), ("sv", "SG90 Servo", "Kilit Kolu", 600, ["SIG", "5V", "GND"])],
                   [("pur", ("D9", 0.2), ("rc", "RST")), ("org", ("D10", 0.3), ("rc", "SDA")), ("ylw", ("D11", 0.4), ("rc", "MOSI")), ("grn", ("D12", 0.5), ("rc", "MISO")), ("blu", ("D13", 0.6), ("rc", "SCK")), ("cyan", ("D6", 0.72), ("sv", "SIG"))])
    guc_hatti(s, [("sv", "5V")], [("rc", "GND"), ("sv", "GND")], v33=[("rc", "3.3V")])
    return s


def sema_step():
    s = proje_kiti("Step Motor Hassas Konumlandırma Kiti", "Arduino UNO + ULN2003 Sürücü + 28BYJ-48 Step Motor — blogdaki kodla birebir uyumludur", "AESTEPSET",
                   ["ULN2003: IN1→D8, IN2→D9, IN3→D10, IN4→D11.", "Kodda Stepper(2048, 8, 10, 9, 11) sırası ULN2003 için doğrudur.",
                    "Sürücü 5V ve GND Arduino'dan; motor 5 pinli soketle sürücüye takılır.", "Uzun süreli kullanımda sürücüyü harici 5V adaptörle besleyin (GND ortak).", "Stepper kütüphanesi IDE ile gelir."],
                   [("uln", "ULN2003", "Step Motor Sürücü", 270, ["IN1", "IN2", "IN3", "IN4", "5V", "GND"]), ("mot", "28BYJ-48", "Step Motor (5 pin soket)", 620, ["  "])],
                   [("org", ("D8", 0.25), ("uln", "IN1")), ("ylw", ("D9", 0.35), ("uln", "IN2")), ("grn", ("D10", 0.45), ("uln", "IN3")), ("blu", ("D11", 0.55), ("uln", "IN4"))])
    guc_hatti(s, [("uln", "5V")], [("uln", "GND")])
    s.tel("blk", [(930, 554), (930, 620)], w=10); s.yazi(945, 595, "5 pinli soket", RENK["gri"], 16)
    return s


def guc_hatti(s, v5, gnd, v33=()):
    """Arduino 5V/3.3V/GND -> modül pinleri (sağ blok)."""
    ax5 = s.pins[("ard", "5V")][0]; ay = 260
    s.tel("red", [(ax5, ay), (ax5, 180), (740, 180)])
    s.yazi(ax5 + 20, 172, "+5V", RENK["red"], 20, True)
    for m, p in v5:
        x, y, _ = s.pins[(m, p)]
        s.tel("red", [(x, y), (740, y), (740, 180)]); s.dugum(740, 180, "red"); s.dugum(x, y, "red")
    if v33:
        ax3 = s.pins[("ard", "3.3V")][0]
        s.tel("org", [(ax3, ay), (ax3, 205), (715, 205)])
        s.yazi(ax3 + 20, 200, "3.3V", RENK["org"], 18, True)
        for m, p in v33:
            x, y, _ = s.pins[(m, p)]
            s.tel("org", [(x, y), (715, y), (715, 205)]); s.dugum(x, y, "org")
    gx, gy, _ = s.pins[("ard", "GND")]
    s.tel("blk", [(gx, gy), (gx, 930), (760, 930)]); s.yazi(gx - 60, 955, "GND", RENK["baslik"], 20, True)
    for m, p in gnd:
        x, y, _ = s.pins[(m, p)]
        s.tel("blk", [(x, y), (690, y), (690, 930)]); s.dugum(690, 930, "blk"); s.dugum(x, y, "blk")
    s.yazi(560, 955, "ORTAK GND HATTI", RENK["baslik"], 18, True, "middle")


def basit_devre(baslik, alt, model, notlar, lamba=True, motor=True, iki_anahtar=False, breadboard=False):
    s = Sema(baslik, alt, model, notlar)
    s.pil("pil", 120, 380, 220, 180, "2'li AA Pil Kutusu = 3V", hucre=("AA 1.5V", "AA 1.5V"))
    px, py, _ = s.pins[("pil", "+")]; nx, ny, _ = s.pins[("pil", "-")]
    if breadboard:
        s.parts.append('<rect x="640" y="160" width="420" height="700" rx="14" fill="#f1f3f6" stroke="#c5ccd6" stroke-width="3"/>')
        for r in range(0, 30):
            for c in range(0, 10):
                s.parts.append(f'<circle cx="{700 + c * 30 + (30 if c >= 5 else 0)}" cy="{190 + r * 22}" r="3" fill="#9aa5b1"/>')
        s.parts.append('<line x1="668" y1="180" x2="668" y2="840" stroke="#e53935" stroke-width="3"/><line x1="684" y1="180" x2="684" y2="840" stroke="#3b6fc4" stroke-width="3"/>')
        s.parts.append('<line x1="1018" y1="180" x2="1018" y2="840" stroke="#e53935" stroke-width="3"/><line x1="1034" y1="180" x2="1034" y2="840" stroke="#3b6fc4" stroke-width="3"/>')
        s.yazi(850, 900, "400 pin küçük breadboard (+ ve − rayları)", RENK["gri"], 16, anchor="middle")
    # anahtar 1
    s.kutu("sw1", 440, 250, 150, 90, RENK["koyu"], "ANAHTAR", "on / off", pins=(("", "l", 0.5), (" ", "r", 0.5)), font=22)
    s.tel("red", [(px, py), (px, 295), (440, 295)]); s.dugum(440, 295, "red")
    if motor:
        s.kutu("mot", 1150, 230, 220, 110, RENK["lacivert"], "DC MOTOR", "3V yassı + pervane", pins=(("", "l", 0.35), (" ", "l", 0.65)), font=24)
        s.parts.append('<circle cx="1420" cy="285" r="40" fill="#e53935"/><circle cx="1420" cy="285" r="12" fill="#b71c1c"/>')
        s.tel("red", [(590, 295), (900, 295), (900, 268.5), (1150, 268.5)]); s.dugum(1150, 268.5, "red")
        s.tel("blk", [(1150, 301.5), (1100, 301.5), (1100, 760), (nx, 760), (nx, ny)]); s.dugum(1150, 301.5, "blk")
    if lamba:
        y = 500
        if iki_anahtar:
            s.kutu("sw2", 440, 470, 150, 90, RENK["koyu"], "ANAHTAR 2", "on / off", pins=(("", "l", 0.5), (" ", "r", 0.5)), font=22)
            s.tel("red", [(px, 295), (px, 515), (440, 515)]); s.dugum(px, 295, "red")
            s.tel("red", [(590, 515), (1150, 515)])
        else:
            s.tel("red", [(590, 295), (700, 295), (700, 515), (1150, 515)]); s.dugum(700, 295, "red")
        s.kutu("lmb", 1150, 470, 220, 100, RENK["kirmizi"], "DUY + AMPUL", "2,5V mini ampul", pins=(("", "l", 0.35), (" ", "l", 0.65)), font=24)
        s.parts.append('<circle cx="1420" cy="520" r="34" fill="#fff8d6" stroke="#e0b100" stroke-width="4"/>')
        s.tel("blk", [(1150, 535), (1100, 535)]); s.dugum(1100, 535, "blk")
    s.yazi(60, 660, "Pil kutusu: kırmızı kablo = +, siyah kablo = −", RENK["gri"], 17)
    return s


def sema_vantilator():
    return basit_devre("Mini Vantilatör Seti", "2'li AA Pil Kutusu + On-Off Anahtar + 3V DC Motor + Pervane — lehim gerektirmez", "AEVANTSET",
                       ["Pil + (kırmızı) → anahtar → motor; motor diğer ucu → pil − (siyah).", "Kablo uçları motor bacaklarına sarılır ya da bantlanır.",
                        "Pervane motor miline bastırarak takılır.", "Motor ters dönerse iki kabloyu yer değiştirin.", "Piller dahil değildir (2 x AA)."], lamba=False)


def sema_fen():
    return basit_devre("Fen Deney Seti", "Küçük Breadboard + 2'li AA Pil Kutusu + Anahtar + 3V DC Motor + Pervane", "AEFENSET",
                       ["Pil + → breadboard + rayı; pil − → − rayı.", "Anahtar ve motor bacakları breadboard deliklerine takılır, jumper ile raylara bağlanır.",
                        "Breadboard'da aynı sütundaki 5 delik birbirine bağlıdır.", "Seri/paralel devre deneyleri için ikinci bir tüketici ekleyin.", "Piller dahil değildir (2 x AA)."], lamba=False, breadboard=True)


def sema_temel():
    return basit_devre("Temel Devre Seti", "Breadboard + Pil Kutusu + 2 Anahtar + DC Motor/Pervane + Duy-Ampul — her tüketici kendi anahtarıyla (paralel devre)", "AETEMELSET",
                       ["Anahtar 1 → motor, Anahtar 2 → lamba; ikisi de pil + hattından beslenir (paralel).", "Seri devre için lamba ve motoru aynı hatta arka arkaya bağlayın.",
                        "Ampul duya çevrilerek takılır; duy vidalı terminalli.", "Jumper kablolu sette bağlantılar jumper ile yapılır.", "Piller dahil değildir (2 x AA)."], lamba=True, motor=True, iki_anahtar=True, breadboard=True)


SEMALAR = {
    "bluetooth-robot": sema_bt, "engelden-kacan-robot": sema_engel, "3u1-robot": sema_3u1,
    "dht11-lcd-kiti": sema_dht, "rtc-lcd-kiti": sema_rtc, "pir-alarm-kiti": sema_alarm,
    "rfid-kilit-kiti": sema_rfid, "step-motor-kiti": sema_step,
    "mini-vantilator-seti": sema_vantilator, "fen-deney-seti": sema_fen, "temel-devre-seti": sema_temel,
}


async def render(adlar):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        for ad in adlar:
            svg = SEMALAR[ad]().svg()
            (OUT / f"{ad}.svg").write_text(svg, encoding="utf-8")
            html = f'<html><body style="margin:0">{svg}</body></html>'
            await pg.set_content(html)
            await pg.screenshot(path=str(OUT / f"{ad}.jpg"), type="jpeg", quality=92, clip={"x": 0, "y": 0, "width": W, "height": H})
            await pg.pdf(path=str(OUT / f"{ad}.pdf"), format="A4", landscape=True, print_background=True,
                         margin={"top": "8mm", "bottom": "8mm", "left": "8mm", "right": "8mm"}, scale=0.62)
            print("OK", ad)
        await b.close()


if __name__ == "__main__":
    secim = sys.argv[1:] or list(SEMALAR)
    asyncio.run(render(secim))
