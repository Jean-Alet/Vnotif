#!/usr/bin/env python3

import time
import json
import logging
import re
import random
import httpx
from pathlib import Path

ACCOUNTS_FILE  = "comptes.txt"
STATE_FILE     = "etat.json"
CHECK_INTERVAL = 3 * 60
LOG_FILE       = "monitor.log"

TOURNAMENT_KEYWORDS = [
    "tournoi", "tournament", "inscription", "inscriptions",
    "open", "competition", "registration",
    "places disponibles", "places limitees", "s'inscrire",
    "inscrivez-vous", "sign up", "signup"
]

# Headers pour les requetes JSON (endpoint __a=1)
_HEADERS_JSON = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux aarch64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "X-IG-App-ID": "936619743392459",
    "Referer": "https://www.instagram.com/",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Linux"',
}

# Headers pour les requetes HTML (page profil)
_HEADERS_HTML = {
    **_HEADERS_JSON,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Dest": "document",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

_session: httpx.Client | None = None


def _make_session() -> httpx.Client:
    """Cree une session et visite la homepage pour obtenir les cookies initiaux."""
    client = httpx.Client(timeout=15, follow_redirects=True)
    try:
        resp = client.get("https://www.instagram.com/", headers=_HEADERS_HTML)
        log.info(f"Session init: HTTP {resp.status_code}, {len(client.cookies)} cookie(s)")
    except httpx.RequestError as e:
        log.warning(f"Session init echec (pas bloquant) : {e}")
    return client


def get_session() -> httpx.Client:
    global _session
    if _session is None or _session.is_closed:
        _session = _make_session()
    return _session


def load_state() -> dict:
    if Path(STATE_FILE).exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state: dict):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def load_accounts() -> list[str]:
    path = Path(ACCOUNTS_FILE)
    if not path.exists():
        log.warning(f"Fichier '{ACCOUNTS_FILE}' introuvable.")
        return []
    accounts = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        accounts.append(line.lstrip("@").lower())
    return accounts


def is_tournament_post(text: str) -> bool:
    return any(kw in text.lower() for kw in TOURNAMENT_KEYWORDS)


def extract_links(text: str) -> list[str]:
    pattern = r'https?://[^\s\]\[)>\"\']+|bit\.ly/\S+|linktr\.ee/\S+'
    return re.findall(pattern, text)


def _parse_edges(edges: list) -> dict | None:
    if not edges:
        return None
    node = edges[0]["node"]
    caption_edges = node.get("edge_media_to_caption", {}).get("edges", [])
    text = caption_edges[0]["node"]["text"] if caption_edges else ""
    post_id = node.get("shortcode", node.get("id", ""))
    return {
        "id": post_id,
        "text": text,
        "timestamp": node.get("taken_at_timestamp", 0),
        "url": f"https://www.instagram.com/p/{post_id}/",
    }


def _fetch_from_html(username: str) -> dict | None:
    """Fallback : scrape la page profil HTML quand l'endpoint JSON echoue."""
    client = get_session()
    try:
        resp = client.get(
            f"https://www.instagram.com/{username}/",
            headers=_HEADERS_HTML,
        )
        if resp.status_code != 200:
            log.warning(f"[{username}] HTML fallback HTTP {resp.status_code}")
            return None

        html = resp.text

        # Tentative via window._sharedData
        m = re.search(r'window\._sharedData\s*=\s*(\{.*?\});\s*</script>', html, re.DOTALL)
        if m:
            data = json.loads(m.group(1))
            edges = (
                data.get("entry_data", {})
                    .get("ProfilePage", [{}])[0]
                    .get("graphql", {})
                    .get("user", {})
                    .get("edge_owner_to_timeline_media", {})
                    .get("edges", [])
            )
            result = _parse_edges(edges)
            if result:
                log.info(f"[{username}] HTML fallback OK (sharedData)")
                return result

        # Fallback minimal : juste le shortcode du dernier post
        shortcodes = re.findall(r'"shortcode"\s*:\s*"([A-Za-z0-9_-]{10,})"', html)
        if shortcodes:
            post_id = shortcodes[0]
            log.info(f"[{username}] HTML fallback OK (shortcode {post_id}, caption indisponible)")
            return {"id": post_id, "text": "", "timestamp": 0, "url": f"https://www.instagram.com/p/{post_id}/"}

        log.warning(f"[{username}] HTML fallback: aucune donnee trouvee")
        return None

    except (httpx.RequestError, json.JSONDecodeError, KeyError, ValueError) as e:
        log.error(f"[{username}] HTML fallback erreur : {e}")
        return None


def fetch_latest_post(username: str) -> dict | None:
    url = f"https://www.instagram.com/{username}/?__a=1&__d=dis"
    client = get_session()

    try:
        resp = client.get(url, headers=_HEADERS_JSON)

        if resp.status_code == 429:
            delay = 600 + random.randint(0, 120)
            log.warning(f"[{username}] Rate-limited. Pause {delay // 60} min.")
            time.sleep(delay)
            return None

        if resp.status_code != 200:
            log.warning(f"[{username}] HTTP {resp.status_code}")
            return None

        data = resp.json()
        edges = (
            data.get("graphql", {})
                .get("user", {})
                .get("edge_owner_to_timeline_media", {})
                .get("edges", [])
        )

        return _parse_edges(edges)

    except httpx.RequestError as e:
        log.error(f"[{username}] Erreur reseau : {e}")
        return None
    except json.JSONDecodeError as e:
        log.error(f"[{username}] Erreur JSON : {e} — reponse brute : {resp.text[:500]!r}")
        log.info(f"[{username}] Tentative fallback HTML...")
        return _fetch_from_html(username)
    except (KeyError, ValueError) as e:
        log.error(f"[{username}] Erreur parsing : {e}")
        return None


def send_notification(username: str, post: dict):
    try:
        from notifier import notify
        notify(username, post)
    except ImportError:
        log.warning("notifier.py introuvable.")
        links = extract_links(post["text"])
        print(f"\nTournoi detecte chez @{username}")
        print(f"Post : {post['url']}")
        if links:
            print(f"Liens : {', '.join(links)}")


def run():
    log.info(f"Monitor demarre. Intervalle : {CHECK_INTERVAL // 60} min.")
    state = load_state()

    while True:
        accounts = load_accounts()

        if not accounts:
            log.warning("Aucun compte dans comptes.txt.")
            time.sleep(300)
            continue

        log.info(f"Verification de {len(accounts)} compte(s)...")

        for username in accounts:
            log.info(f"  @{username}")
            post = fetch_latest_post(username)

            if post is None:
                continue

            if post["id"] != state.get(username):
                state[username] = post["id"]
                save_state(state)

                if is_tournament_post(post["text"]):
                    log.info(f"  Tournoi detecte chez @{username}")
                    send_notification(username, post)
                else:
                    log.info(f"  Nouveau post, pas un tournoi.")
            else:
                log.info(f"  Aucun nouveau post.")

            time.sleep(5)

        log.info(f"Prochaine verification dans {CHECK_INTERVAL // 60} min.\n")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    run()
