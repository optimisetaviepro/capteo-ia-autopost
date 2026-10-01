#!/usr/bin/env python3
"""Programme dans Buffer les éléments de planning.json dus dans les prochaines heures.

Usage :
    BUFFER_API_KEY=... python scripts/schedule.py            # programmation réelle
    python scripts/schedule.py --dry-run                      # vérifie le planning, n'appelle pas Buffer

Variables d'environnement :
    BUFFER_API_KEY     clé API Buffer (obligatoire hors --dry-run)
    GITHUB_REPOSITORY  "pseudo/depot" (fourni par GitHub Actions) pour construire les URL raw
    MEDIA_BRANCH       branche qui sert les images (défaut : main)
    WINDOW_HOURS       taille de la fenêtre de programmation (défaut : 30)
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

API_URL = "https://api.buffer.com"
ROOT = Path(__file__).resolve().parent.parent
MEDIA_DIR = ROOT / "media"
USER_AGENT = "capteo-ia-autopost/1.0"


def fail(msg):
    print(f"::error::{msg}" if os.getenv("GITHUB_ACTIONS") else f"ERREUR : {msg}")
    sys.exit(1)


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
        else:
            fail(f"item {i} : type inconnu '{it['type']}' (carousel ou story)")
        items.append({**it, "at": at, "files": files})
    return data, items


def media_url(repo, branch, path):
    rel = path.relative_to(ROOT).as_posix()
    return f"https://raw.githubusercontent.com/{repo}/{branch}/{rel}"


def check_url(url):
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status == 200
    except urllib.error.HTTPError:
        return False


def gql(api_key, query, variables=None):
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(API_URL, data=body, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            payload = json.load(r)
    except urllib.error.HTTPError as e:
        fail(f"HTTP {e.code} de l'API Buffer : {e.read().decode(errors='replace')[:500]}")
    if payload.get("errors"):
        fail(f"Erreur GraphQL : {json.dumps(payload['errors'], ensure_ascii=False)[:500]}")
    return payload["data"]


EXISTING_QUERY = """
query($input: PostsInput!, $after: String) {
  posts(first: 100, after: $after, input: $input) {
    edges { node { id dueAt status } }
    pageInfo { hasNextPage endCursor }
  }
}"""

CREATE_MUTATION = """
mutation($input: CreatePostInput!) {
  createPost(input: $input) {
    ... on PostActionSuccess { post { id dueAt } }
    ... on MutationError { message }
  }
}"""


def existing_due_times(api_key, org_id, channel_id, start, end):
    """dueAt (à la seconde) des posts déjà présents sur le channel dans la fenêtre."""
    seen, after = set(), None
    while True:
        data = gql(api_key, EXISTING_QUERY, {"after": after, "input": {
            "organizationId": org_id,
            "filter": {
                "channelIds": [channel_id],
                "dueAt": {"start": iso(start - timedelta(minutes=1)), "end": iso(end + timedelta(minutes=1))},
                "status": ["scheduled", "sending", "sent", "needs_approval", "draft", "error"],
            },
        }})["posts"]
        for edge in data["edges"] or []:
            if edge["node"]["dueAt"]:
                seen.add(parse_utc(edge["node"]["dueAt"]))
        if not data["pageInfo"]["hasNextPage"]:
            return seen
        after = data["pageInfo"]["endCursor"]


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_utc(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc).replace(microsecond=0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="n'appelle pas Buffer")
    ap.add_argument("--now", help="date ISO pour simuler une exécution (tests)")
    args = ap.parse_args()

    data, items = load_planning()
    print(f"Planning OK : {len(items)} éléments, du {items[0]['at']:%d/%m} au {items[-1]['at']:%d/%m}")

    now = datetime.fromisoformat(args.now) if args.now else datetime.now(timezone.utc)
    window = int(os.getenv("WINDOW_HOURS", "30"))
    end = now + timedelta(hours=window)
    due = [it for it in items if now < it["at"] <= end]
    print(f"Fenêtre : {iso(now)} → {iso(end)} ({window} h)")

    repo = os.getenv("GITHUB_REPOSITORY", "PSEUDO/capteo-ia-autopost")
    branch = os.getenv("MEDIA_BRANCH", "main")

    if args.dry_run:
        for it in due:
            print(f"  [dry-run] {it['at']:%d/%m %H:%M} {it['type']:8} {len(it['files'])} image(s) — {it['media']}")
        if not due:
            print("Rien à programmer dans la fenêtre.")
        return

    api_key = os.getenv("BUFFER_API_KEY")
    if not api_key:
        fail("BUFFER_API_KEY manquante (secret GitHub non défini ?)")

    account = gql(api_key, "query { account { id organizations { id name } } }")["account"]
    orgs = {o["id"]: o["name"] for o in account["organizations"]}
    if data["organization_id"] not in orgs:
        fail(f"L'organisation {data['organization_id']} n'est pas accessible avec cette clé")
    print(f"Connexion Buffer OK (organisation « {orgs[data['organization_id']]} »)")

    if not due:
        print("Rien à programmer dans la fenêtre.")
        return

    already = existing_due_times(api_key, data["organization_id"], data["channel_id"], now, end)
    created = skipped = errors = 0
    for it in due:
        label = f"{it['at']:%d/%m %H:%M} {it['type']} {it['media']}"
        if it["at"].astimezone(timezone.utc).replace(microsecond=0) in already:
            print(f"  = déjà programmé : {label}")
            skipped += 1
            continue
        urls = [media_url(repo, branch, f) for f in it["files"]]
        missing = [u for u in urls if not check_url(u)]
        if missing:
            print(f"  ✗ image inaccessible (dépôt privé ou fichier non poussé ?) : {missing[0]}")
            errors += 1
            continue
        post_input = {
            "channelId": data["channel_id"],
            "text": it.get("text", ""),
            "assets": [{"image": {"url": u}} for u in urls],
            "dueAt": iso(it["at"]),
            "mode": "customScheduled",
            "schedulingType": "automatic",
            "metadata": {"instagram": {
                "type": "story" if it["type"] == "story" else "post",
                "shouldShareToFeed": True,
            }},
        }
        res = gql(api_key, CREATE_MUTATION, {"input": post_input})["createPost"]
        if "post" in res:
            print(f"  ✓ programmé : {label} (id {res['post']['id']})")
            created += 1
        else:
            print(f"  ✗ refusé par Buffer : {label} — {res.get('message')}")
            errors += 1

    print(f"Bilan : {created} programmé(s), {skipped} déjà présent(s), {errors} erreur(s)")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
