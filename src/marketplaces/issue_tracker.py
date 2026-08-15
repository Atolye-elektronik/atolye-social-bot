"""
Platform-agnostic "tek issue'yu güncel tut" yardımcısı.

Sipariş senkron scriptleri (trendyol_sync.py, hepsiburada_sync.py) bekleyen
siparişleri tek bir açık issue'da listeler. Bu modül o issue'yu hem GitHub'da
hem GitLab'da yönetebilir — hangi ortamda çalıştığını ortam değişkenlerinden
kendisi anlar:

GitLab  : GITLAB_TOKEN + CI_PROJECT_ID (CI_API_V4_URL otomatik gelir)
GitHub  : GITHUB_TOKEN + GITHUB_REPOSITORY

İkisi de yoksa (yerel çalıştırma) sessizce atlar ve False döner.
"""

import os

import requests


def _gitlab_config():
    token = os.environ.get("GITLAB_TOKEN")
    project_id = os.environ.get("CI_PROJECT_ID")
    if not (token and project_id):
        return None
    api = os.environ.get("CI_API_V4_URL", "https://gitlab.com/api/v4")
    return {
        "url": f"{api}/projects/{project_id}/issues",
        "headers": {"PRIVATE-TOKEN": token},
    }


def _github_config():
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not (token and repo):
        return None
    return {
        "url": f"https://api.github.com/repos/{repo}/issues",
        "headers": {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
    }


def upsert_issue(title, body, labels, create_if_missing=True):
    """Aynı başlıklı açık issue varsa gövdesini günceller, yoksa açar.

    Returns True if an issue was created/updated, False if skipped."""
    cfg = _gitlab_config()
    is_gitlab = cfg is not None
    if cfg is None:
        cfg = _github_config()
    if cfg is None:
        print("Issue API bilgisi yok (GITLAB_TOKEN / GITHUB_TOKEN) — issue adımı atlanıyor.")
        return False

    # Açık issue'lar arasında aynı başlıklıyı ara
    params = {"state": "opened" if is_gitlab else "open", "per_page": 100}
    resp = requests.get(cfg["url"], headers=cfg["headers"], params=params, timeout=30)
    resp.raise_for_status()
    existing = next((i for i in resp.json() if i.get("title") == title), None)

    if existing:
        # GitLab güncellemeyi PUT ile, GitHub PATCH ile kabul ediyor
        number = existing["iid"] if is_gitlab else existing["number"]
        method = "PUT" if is_gitlab else "PATCH"
        payload = {"description": body} if is_gitlab else {"body": body}
        requests.request(
            method, f"{cfg['url']}/{number}", headers=cfg["headers"], json=payload, timeout=30
        ).raise_for_status()
        print(f"Issue #{number} güncellendi.")
        return True

    if not create_if_missing:
        print("Bekleyen kayıt yok, yeni issue açılmadı.")
        return False

    payload = (
        {"title": title, "description": body, "labels": ",".join(labels)}
        if is_gitlab
        else {"title": title, "body": body, "labels": labels}
    )
    r = requests.post(cfg["url"], headers=cfg["headers"], json=payload, timeout=30)
    r.raise_for_status()
    created = r.json()
    print(f"Yeni issue oluşturuldu: #{created.get('iid') or created.get('number')}")
    return True
