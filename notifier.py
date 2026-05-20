import httpx
import logging
import re

log = logging.getLogger(__name__)

NTFY_TOPIC  = "volley-gojo-glazer-6x7q"
NTFY_SERVER = "https://ntfy.sh"


def extract_links(text: str) -> list[str]:
    pattern = r'https?://[^\s\]\[)>\"\']+|bit\.ly/\S+|linktr\.ee/\S+'
    return re.findall(pattern, text)


def notify(username: str, post: dict):
    links = extract_links(post["text"])
    link = links[0] if links else post["url"]

    try:
        resp = httpx.post(
            f"{NTFY_SERVER}/{NTFY_TOPIC}",
            data=f"Tournoi chez @{username}\n{link}".encode("utf-8"),
            headers={
                "Title":    f"Tournoi @{username}",
                "Priority": "urgent",
                "Tags":     "volleyball",
                "Click":    link,
            },
            timeout=10
        )
        if resp.status_code == 200:
            log.info("Notification envoyee.")
        else:
            log.error(f"ntfy erreur {resp.status_code} : {resp.text}")
    except httpx.RequestError as e:
        log.error(f"Erreur envoi notification : {e}")