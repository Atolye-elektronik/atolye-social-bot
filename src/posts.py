"""posts/ klasöründeki markdown post dosyalarını okur.

Bir post dosyası şöyle görünür:

    ---
    platforms: [instagram, facebook]
    media: posts/media/urun1.jpg
    publish_at: 2026-08-01 10:00
    ---
    Buraya paylaşım metni gelir.
    Birden fazla satır olabilir. #atolyeelektronik

`publish_at` boş bırakılırsa post ilk çalışmada paylaşılır.
Saat dilimi Europe/Istanbul kabul edilir.
"""

from __future__ import annotations

import datetime as dt
import pathlib
import re
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Istanbul")
POSTS_DIR = pathlib.Path("posts")

FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)


@dataclass
class Post:
    slug: str
    path: pathlib.Path
    platforms: list[str]
    caption: str
    media: str | list[str] | None = None
    publish_at: dt.datetime | None = None
    extra: dict = field(default_factory=dict)

    @property
    def is_carousel(self) -> bool:
        return isinstance(self.media, list) and len(self.media) > 1

    @property
    def media_list(self) -> list[str]:
        if not self.media:
            return []
        if isinstance(self.media, list):
            return self.media
        return [self.media]

    @property
    def is_video(self) -> bool:
        if not self.media or isinstance(self.media, list):
            return False
        return self.media.lower().endswith((".mp4", ".mov", ".m4v"))

    def is_due(self, now: dt.datetime | None = None) -> bool:
        if self.publish_at is None:
            return True
        now = now or dt.datetime.now(TZ)
        return self.publish_at <= now


    @property
    def tiktok_media(self) -> str:
        """TikTok'a gidecek video dosyasi — **sessiz kopya**.

        28.08: Pinterest, bu videolardaki arka plan muziginden telif verdi.
        TikTok yuklemede ayni denetimi yapiyor; takilan video sessize
        aliniyor ve sessize alinan video dagitim da alamiyor. Muzigin
        katkisi, dagitimi kaybetme riskine degmiyor.

        Sessiz kopya `posts/media/sessiz/` altinda tutuluyor ve yalnizca bir
        kez uretiliyor; video akisi kopyalandigi icin yeniden kodlama yok.
        Instagram ve YouTube kopyalari sesli kalmaya devam ediyor.
        """
        if not self.is_video:
            return self.media
        return str(sessiz_kopya(pathlib.Path(self.media)))

    @property
    def tiktok_caption(self) -> str:
        """TikTok'a gidecek metin.

        26.08 analizi: 23-25 Agustos videolari 2 ve 0 izlenmede kaldi. Ayni
        metin uc platforma birden gidiyordu; icinde YouTube'un #Shorts etiketi
        ve siteye giden link vardi. TikTok rakip platform etiketini ve disari
        trafik goturen linki dagitimda asagi cekiyor. Bu yuzden TikTok metni
        artik ayri uretiliyor: link yok, #Shorts yok, kanca en uste.
        """
        return tiktok_metni(self.caption)


def _parse_scalar(raw: str):
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1]
        return [x.strip().strip("'\"") for x in inner.split(",") if x.strip()]
    return raw.strip("'\"")


def _parse_front_matter(text: str) -> dict:
    data: dict = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        data[key.strip()] = _parse_scalar(value)
    return data


def parse_datetime(raw) -> dt.datetime | None:
    if not raw or not isinstance(raw, str):
        return None
    raw = raw.strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            parsed = dt.datetime.strptime(raw, fmt)
            return parsed.replace(tzinfo=TZ)
        except ValueError:
            continue
    raise ValueError(f"publish_at okunamadı: {raw!r} (beklenen biçim: 2026-08-01 10:00)")


def load_post(path: pathlib.Path) -> Post:
    text = path.read_text(encoding="utf-8")
    match = FRONT_MATTER_RE.match(text)
    if not match:
        raise ValueError(
            f"{path} dosyasında front matter bulunamadı. "
            "Dosya '---' satırıyla başlamalı."
        )

    meta = _parse_front_matter(match.group(1))
    caption = match.group(2).strip()

    platforms = meta.get("platforms") or ["instagram", "facebook"]
    if isinstance(platforms, str):
        platforms = [platforms]
    platforms = [p.strip().lower() for p in platforms]

    media = meta.get("media") or None
    if isinstance(media, list) and len(media) == 1:
        media = media[0]

    return Post(
        slug=path.stem,
        path=path,
        platforms=platforms,
        caption=caption,
        media=media,
        publish_at=parse_datetime(meta.get("publish_at")),
        extra=meta,
    )


def load_all(directory: pathlib.Path = POSTS_DIR) -> list[Post]:
    if not directory.exists():
        return []
    found = []
    for path in sorted(directory.glob("*.md")):
        if path.name.upper() == "README.MD":
            continue
        found.append(load_post(path))
    return found


# --- TikTok metni ------------------------------------------------------------
# TikTok'ta dagitimi dusuren iki sey vardi (26.08 analizi):
#   * #Shorts  -> YouTube'un etiketi; rakip platform sinyali
#   * site linki -> platform disina trafik
# Ayrica ilk satir kanca olmali; katalog adiyla baslayan videolar 1. saniyede
# terk ediliyordu (ort. izlenme 1.4 sn, tamamlanma %0).

LINK_RE = re.compile(r"https?://\S+")
YASAKLI_ETIKET = {"shorts", "short", "youtube", "youtubeshorts", "reels", "reel"}
# "Siparis 👉" gibi linke goturen cagri satirlari linksiz anlamsiz kaliyor.
CTA_SATIR_RE = re.compile(r"^\s*(sipari[sş]|link|detay|incele)\b.*", re.IGNORECASE)



def sessiz_kopya(video: pathlib.Path) -> pathlib.Path:
    """Videonun sesi alinmis kopyasini dondurur, yoksa uretir.

    ffmpeg yoksa ya da uretim basarisiz olursa **sessizce orijinali
    donduruyor**: ses yuzunden bir paylasimi hic yapmamak, sesli paylasmaktan
    daha kotu.
    """
    import shutil
    import subprocess

    if not video.exists():
        return video
    hedef = video.parent / "sessiz" / video.name
    if hedef.exists() and hedef.stat().st_mtime >= video.stat().st_mtime:
        return hedef

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return video
    hedef.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run([ffmpeg, "-v", "error", "-y", "-i", str(video),
                        "-c:v", "copy", "-an", "-movflags", "+faststart",
                        str(hedef)], check=True)
    except Exception:
        return video
    return hedef


def tiktok_metni(caption: str) -> str:
    """Ortak post metnini TikTok'a uygun hale getirir."""
    satirlar = []
    for ham in caption.splitlines():
        linkli = LINK_RE.search(ham) is not None
        satir = LINK_RE.sub("", ham).rstrip()
        # Linki cikinca geriye sadece "Siparis 👉" gibi bir cagri kaliyorsa
        # satirin tamamini at.
        if linkli and CTA_SATIR_RE.match(satir):
            continue
        if satir.strip() in {"", "👉", "->"}:
            satirlar.append("")
            continue
        satirlar.append(satir)

    metin = "\n".join(satirlar)

    # Rakip platform etiketlerini ele.
    def _etiket_ele(m: re.Match) -> str:
        return "" if m.group(1).lower() in YASAKLI_ETIKET else m.group(0)

    metin = re.sub(r"#(\w+)", _etiket_ele, metin)

    # Fazla bosluklari topla.
    metin = re.sub(r"[ \t]{2,}", " ", metin)
    metin = re.sub(r"\n{3,}", "\n\n", metin).strip()
    return metin
