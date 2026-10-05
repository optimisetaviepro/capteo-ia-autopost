#!/usr/bin/env python3
"""Programme dans Buffer les éléments de planning.json, et rattrape ceux qui ont été manqués.

Lancé toutes les heures par GitHub Actions. À chaque passage, pour chaque réseau :
  1. programme les éléments dus dans les WINDOW_HOURS prochaines heures (24 h par défaut) ;
  2. publie immédiatement les éléments dont l'heure est passée depuis moins de CATCHUP_HOURS
     (6 h par défaut) et qui n'ont jamais été publiés, ou dont la publication a échoué ;
  3. ne crée jamais de doublon : un post déjà présent dans Buffer (même texte, ou même image
     pour une story, ou même heure) est ignoré.
Le passage échoue (et GitHub envoie un mail) si un élément n'a pas pu être programmé ou publié,
ou si le planning se termine dans moins de PLANNING_ALERT_DAYS jours.

Usage :
    BUFFER_API_KEY=... python scripts/schedule.py            # programmation réelle
    python scripts/schedule.py --dry-run [--now ISO]          # vérifie le planning, n'appelle pas Buffer

Variables d'environnement :
    BUFFER_API_KEY       clé API Buffer (obligatoire hors --dry-run)
    GITHUB_REPOSITORY    "pseudo/depot" (fourni par GitHub Actions) pour construire les URL raw
    MEDIA_BRANCH         branche qui sert les images (défaut : main)
    WINDOW_HOURS         fenêtre de programmation (défaut : 24, garde sous la limite de 10 posts Buffer)
    CATCHUP_HOURS        rattrapage des éléments manqués (défaut : 6)
    PLANNING_ALERT_DAYS  alerte quand le planning se termine bientôt (défaut : 3)
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

API_URL = "https://api.buffer.com"
ROOT = Path(__file__).resolve().parent.parent
MEDIA_DIR = ROOT / "media"
USER_AGENT = "capteo-ia-autopost/2.0"


class BufferError(Exception):
    pass


def fail(msg):
    print(f"::error::{msg}" if os.getenv("GITHUB_ACTIONS") else f"ERREUR : {msg}")
    sys.exit(1)


def alert(msg):
    print(f"::error::{msg}" if os.getenv("GITHUB_ACTIONS") else f"ALERTE : {msg}")


def load_planning():
    data = json.loads((ROOT / "planning.json").read_text(encoding="utf-8"))
    items = []
    for i, it in enumerate(data["items"]):
        at = datetime.fromisoformat(it["at"])
        if at.tzinfo is None:
            fail(f"item {i} : 'at' doit contenir un fuseau (ex. +02:00) : {it['at']}")
        if it["type"] == "carousel":
            files = sorted((MEDIA_DIR / it["media"]).glob("*.png"), key=lambda p: int(p.stem))
            if not 2 <= len(files) <= 10:
                fail(f"item {i} : un carrousel doit avoir 2 à 10 images, trouvé {len(files)} dans media/{it['media']}")
        elif it["type"] == "story":
            files = [MEDIA_DIR / it["media"]]
            if not files[0].is_file():
                fail(f"item {i} : fichier introuvable media/{it['media']}")
        elif it["type"] == "video":
            # Reel Instagram + vidéo TikTok : media = "v/NN-slug.mp4" ; "cover_ms" = image de couverture
            # (les réseaux n'acceptent pas de miniature personnalisée, seulement un instant de la vidéo).
            files = [MEDIA_DIR / it["media"]]
            if not files[0].is_file() or files[0].suffix != ".mp4":
                fail(f"item {i} : vidéo introuvable media/{it['media']}")
        else:
            fail(f"item {i} : type inconnu '{it['type']}' (carousel, story ou video)")
        items.append({**it, "at": at, "files": files})
    items.sort(key=lambda it: it["at"])
    return data, items


def media_url(repo, branch, path):
    rel = path.relative_to(ROOT).as_posix()
    return f"https://raw.githubusercontent.com/{repo}/{branch}/{rel}"


def check_url(url):
    for attempt in range(3):
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status == 200
        except urllib.error.HTTPError as e:
            if e.code < 500:
                return False
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            pass
        time.sleep(5 * (attempt + 1))
    return False


def gql(api_key, query, variables=None):
    """Appel GraphQL avec 4 tentatives sur les erreurs réseau / 5xx / 429. Lève BufferError sinon."""
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(API_URL, data=body, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    })
    last = None
    for attempt in range(1, 5):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                payload = json.load(r)
            if payload.get("errors"):
                raise BufferError(f"Erreur GraphQL : {json.dumps(payload['errors'], ensure_ascii=False)[:500]}")
            return payload["data"]
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code} : {e.read().decode(errors='replace')[:300]}"
            if e.code < 500 and e.code != 429:
                raise BufferError(last)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = f"réseau : {e}"
        if attempt < 4:
            print(f"  … Buffer indisponible ({last}), nouvelle tentative dans {20 * attempt} s")
            time.sleep(20 * attempt)
    raise BufferError(f"API Buffer injoignable après 4 tentatives ({last})")


EXISTING_QUERY = """
query($input: PostsInput!, $after: String) {
  posts(first: 100, after: $after, input: $input) {
    edges { node { id dueAt status text assets { source } } }
    pageInfo { hasNextPage endCursor }
  }
}"""

CREATE_MUTATION = """
mutation($input: CreatePostInput!) {
  createPost(input: $input) {
    ... on PostActionSuccess { post { id dueAt status } }
    ... on MutationError { message }
  }
}"""


def norm(text):
    return " ".join((text or "").split())[:80]


def item_keys(it, urls):
    keys = {("due", it["at"].astimezone(timezone.utc).replace(microsecond=0))}
    if norm(it.get("text")):
        keys.add(("text", norm(it["text"])))
    else:
        keys.add(("asset", urls[0]))
    return keys


def post_keys(node):
    keys = set()
    if node["dueAt"]:
        keys.add(("due", parse_utc(node["dueAt"])))
    if norm(node.get("text")):
        keys.add(("text", norm(node["text"])))
    elif node.get("assets"):
        keys.add(("asset", node["assets"][0]["source"]))
    return keys


def existing_posts(api_key, org_id, channel_id, start, end):
    """(clés des posts valides, clés des posts en erreur) du channel dans la période."""
    ok, failed, after = set(), set(), None
    while True:
        data = gql(api_key, EXISTING_QUERY, {"after": after, "input": {
            "organizationId": org_id,
            "filter": {
                "channelIds": [channel_id],
                "dueAt": {"start": iso(start), "end": iso(end)},
                "status": ["scheduled", "sending", "sent", "needs_approval", "draft", "error"],
            },
        }})["posts"]
        for edge in data["edges"] or []:
            node = edge["node"]
            (failed if node["status"] == "error" else ok).update(post_keys(node))
        if not data["pageInfo"]["hasNextPage"]:
            return ok, failed
        after = data["pageInfo"]["endCursor"]


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_utc(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc).replace(microsecond=0)


def post_metadata(network, it):
    video = it["type"] == "video"
    if network == "tiktok":
        # Titre du post TikTok : 1re ligne du texte, 90 caractères max.
        first_line = it.get("text", "").strip().split("\n")[0]
        meta = {"title": first_line[:90]}
        if video:
            # Label « contenu généré par IA » : activé par défaut, "ai_label": false pour le test A/B
            # (motion design codé, pas d'image réaliste générée).
            meta["isAiGenerated"] = it.get("ai_label", True)
        return {"tiktok": meta}
    meta = {"type": "reel" if video else ("story" if it["type"] == "story" else "post"), "shouldShareToFeed": True}
    if video:
        meta["isAiGenerated"] = it.get("ai_label", True)
    return {"instagram": meta}


def post_assets(it, urls):
    if it["type"] == "video":
        video = {"url": urls[0]}
        if it.get("cover_ms") is not None:
            video["metadata"] = {"thumbnailOffset": int(it["cover_ms"])}
        return [{"video": video}]
    return [{"image": {"url": u}} for u in urls]


def on_network(network, it):
    """La clé "networks" (liste) choisit les réseaux d'un élément ; sinon TikTok reçoit carrousels et vidéos,
    Instagram reçoit tout."""
    if "networks" in it:
        return network in it["networks"]
    return network != "tiktok" or it["type"] in ("carousel", "video")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="n'appelle pas Buffer")
    ap.add_argument("--now", help="date ISO pour simuler une exécution (tests)")
    args = ap.parse_args()

    data, items = load_planning()
    print(f"Planning OK : {len(items)} éléments, du {items[0]['at']:%d/%m} au {items[-1]['at']:%d/%m}")

    now = datetime.fromisoformat(args.now) if args.now else datetime.now(timezone.utc)
    window = float(os.getenv("WINDOW_HOURS", "24"))
    catchup = float(os.getenv("CATCHUP_HOURS", "6"))
    alert_days = float(os.getenv("PLANNING_ALERT_DAYS", "3"))
    start, end = now - timedelta(hours=catchup), now + timedelta(hours=window)
    due = [it for it in items if start < it["at"] <= end]
    print(f"Fenêtre : rattrapage depuis {iso(start)}, programmation jusqu'à {iso(end)}")

    problems = []
    remaining = items[-1]["at"] - now
    # Une seule alerte par jour (passage de 16h UTC), pas une par heure.
    if remaining < timedelta(days=alert_days) and (args.now or now.hour == 16):
        problems.append(f"Le planning se termine le {items[-1]['at']:%d/%m à %H:%M} : "
                        f"ajoute de nouveaux carrousels (voir README).")

    repo = os.getenv("GITHUB_REPOSITORY", "PSEUDO/capteo-ia-autopost")
    branch = os.getenv("MEDIA_BRANCH", "main")

    channels = [("instagram", data["channel_id"])]
    if data.get("tiktok_channel_id"):
        channels.append(("tiktok", data["tiktok_channel_id"]))

    if args.dry_run:
        for network, _ in channels:
            for it in due:
                if not on_network(network, it):
                    continue
                mode = "rattrapage" if it["at"] <= now else "programmé"
                print(f"  [dry-run] {network:9} {it['at']:%d/%m %H:%M} {it['type']:8} {mode:10} {it['media']}")
        for p in problems:
            alert(p)
        return

    api_key = os.getenv("BUFFER_API_KEY")
    if not api_key:
        fail("BUFFER_API_KEY manquante (secret GitHub non défini ?)")

    try:
        account = gql(api_key, "query { account { id organizations { id name } } }")["account"]
    except BufferError as e:
        fail(str(e))
    orgs = {o["id"]: o["name"] for o in account["organizations"]}
    if data["organization_id"] not in orgs:
        fail(f"L'organisation {data['organization_id']} n'est pas accessible avec cette clé")
    print(f"Connexion Buffer OK (organisation « {orgs[data['organization_id']]} »)")

    created = caught_up = skipped = 0
    for network, channel_id in channels:
        todo = [it for it in due if on_network(network, it)]
        if not todo:
            continue
        try:
            ok, failed = existing_posts(api_key, data["organization_id"], channel_id,
                                        start - timedelta(hours=1), end + timedelta(minutes=5))
        except BufferError as e:
            problems.append(f"{network} : lecture des posts existants impossible ({e})")
            continue
        for it in todo:
            label = f"{network:9} {it['at']:%d/%m %H:%M} {it['type']} {it['media']}"
            urls = [media_url(repo, branch, f) for f in it["files"]]
            keys = item_keys(it, urls)
            if keys & ok:
                skipped += 1
                continue
            late = it["at"] <= now
            if keys & failed:
                print(f"  ! publication en erreur dans Buffer, nouvel essai : {label}")
            missing = [u for u in urls if not check_url(u)]
            if missing:
                problems.append(f"fichier inaccessible pour {label} : {missing[0]}")
                continue
            post_input = {
                "channelId": channel_id,
                "text": it.get("text", ""),
                "assets": post_assets(it, urls),
                "mode": "shareNow" if late else "customScheduled",
                "schedulingType": "automatic",
                "metadata": post_metadata(network, it),
            }
            if not late:
                post_input["dueAt"] = iso(it["at"])
            try:
                res = gql(api_key, CREATE_MUTATION, {"input": post_input})["createPost"]
            except BufferError as e:
                problems.append(f"{label} : {e}")
                continue
            if "post" in res:
                if late:
                    print(f"  ⚡ rattrapé, publié maintenant : {label} (id {res['post']['id']})")
                    caught_up += 1
                else:
                    print(f"  ✓ programmé : {label} (id {res['post']['id']})")
                    created += 1
                ok |= keys
            else:
                problems.append(f"refusé par Buffer : {label} — {res.get('message')}")

    print(f"Bilan : {created} programmé(s), {caught_up} rattrapé(s), {skipped} déjà en place, "
          f"{len(problems)} problème(s)")
    for p in problems:
        alert(p)
    if problems:
        sys.exit(1)


if __name__ == "__main__":
    main()
