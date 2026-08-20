#!/usr/bin/env bash
# state/ degisikliklerini catisma olsa bile kaybetmeden main'e iter.
#
# Iki kosu ayni anda yayin kaydina yazinca "git pull --rebase" catisma
# verip isi dusuruyordu (20.08). Burada catisma cikarsa published.json
# JSON duzeyinde BIRLESTIRILIYOR — hicbir platform kaydi kaybolmuyor,
# boylece bir sonraki tur ayni postu tekrar paylasmiyor.
set -u
MESAJ="${1:-durum guncellendi}"

if [ -z "$(git status --porcelain state/)" ]; then
  echo "Kayitta degisiklik yok."
  exit 0
fi

git config user.name "atolye-bot"
git config user.email "bot@users.noreply.github.com"

for deneme in 1 2 3 4 5; do
  git add state/
  git diff --staged --quiet || git commit -m "chore: ${MESAJ} [skip ci]"

  if git push 2>/dev/null; then
    echo "Kayit itildi (deneme ${deneme})."
    exit 0
  fi

  echo "Uzakta yeni kayit var, birlestiriliyor (deneme ${deneme})..."
  git fetch origin main
  # Kendi surumumuzu sakla, uzaktakini al, ikisini birlestir.
  cp state/published.json /tmp/bizim.json 2>/dev/null || true
  git reset --hard origin/main
  if [ -f /tmp/bizim.json ]; then
    python - <<'PY'
import json, pathlib
uzak = pathlib.Path("state/published.json")
bizim = json.loads(pathlib.Path("/tmp/bizim.json").read_text(encoding="utf-8"))
mevcut = json.loads(uzak.read_text(encoding="utf-8")) if uzak.exists() else {}
for slug, platformlar in bizim.items():
    mevcut.setdefault(slug, {}).update(platformlar)
uzak.write_text(json.dumps(mevcut, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8")
print(f"birlestirildi: {len(mevcut)} post kaydi")
PY
  fi
  sleep 3
done

echo "UYARI: kayit 5 denemede itilemedi." >&2
exit 1
