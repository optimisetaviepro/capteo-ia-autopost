#!/usr/bin/env python3
"""Relève les statistiques des posts publiés via Buffer et écrit le tableau de bord des tests.

Chaque post publié est relié à son élément de planning.json par l'URL de son média, ce qui donne
ses caractéristiques de test : format, créneau, réseau, version d'accroche (v1 / v2 / v3), label IA.

Sorties (dans stats/) :
    posts.csv     une ligne par post publié, avec ses statistiques
    RAPPORT.md    meilleurs posts et comparaison de chaque test A/B

Usage :
    BUFFER_API_KEY=... python scripts/metrics.py [--days 30]

Les statistiques Buffer sont rafraîchies une fois par jour : un post de moins de 36 h est marqué
« trop récent » et exclu des comparaisons.
"""
import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from schedule import BufferError, gql, iso, norm, on_network, parse_utc  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "stats"
METRICS = ["views", "reach", "reactions", "comments", "shares", "saves", "follows", "averageTimeWatched"]
MIN_AGE = timedelta(hours=36)

QUERY = """
query($input: PostsInput!, $after: String) {
  posts(first: 100, after: $after, input: $input) {
    edges { node { id sentAt channelId channelService text assets { source type } metrics { type value } } }
    pageInfo { hasNextPage endCursor }
  }
}"""


def media_key(url):
    """'.../media/c/24/1.png' -> 'c/24' ; '.../media/v/01-nova.mp4' -> 'v/01-nova.mp4'."""
    if "/media/" not in url:
        return None
    rel = url.split("/media/", 1)[1]
    return rel.rsplit("/", 1)[0] if rel.startswith(("c/", "t/")) else rel


def fetch(api_key, org_id, start):
    after, posts = None, []
    while True:
        data = gql(api_key, QUERY, {"after": after, "input": {
            "organizationId": org_id,
            "filter": {"status": ["sent"], "dueAt": {"start": iso(start)}},
        }})["posts"]
        posts += [e["node"] for e in data["edges"] or []]
        if not data["pageInfo"]["hasNextPage"]:
            return posts
        after = data["pageInfo"]["endCursor"]


def paris(dt):
    """Heure de Paris (heure d'été jusqu'au 25/10/2026), suffisante pour classer les créneaux."""
    return dt + timedelta(hours=2 if dt < datetime(2026, 10, 25, 1, tzinfo=timezone.utc) else 1)


def rows_from(posts, planning, now):
    by_media = {it["media"]: it for it in planning["items"]}
    # TikTok ne renvoie pas l'URL des médias : on relie alors le post par réseau + début du texte.
    by_text = {(net, norm(it.get("text"))): it for it in planning["items"] if it.get("text")
               for net in ("tiktok", "instagram") if on_network(net, it)}
    rows = []
    for p in posts:
        assets = p.get("assets") or [{}]
        src = assets[0].get("source", "")
        it = by_media.get(media_key(src) or "", {}) or by_text.get((p["channelService"], norm(p["text"])), {})
        if not it:  # post fait à la main dans Buffer : format déduit des médias
            kind = "video" if assets[0].get("type") == "video" else "carousel" if len(assets) > 1 else "image"
            it = {"type": kind}
        m = {x["type"]: x["value"] for x in p.get("metrics") or []}
        sent = parse_utc(p["sentAt"])
        rows.append({
            "date": paris(sent).strftime("%Y-%m-%d"),
            "heure": paris(sent).strftime("%H:%M"),
            "creneau": f"{paris(sent).hour}h",
            "reseau": p["channelService"],
            "format": it.get("format", it.get("type", "inconnu")),
            "media": it.get("media", ""),
            "accroche": it.get("hook", "v1") if it.get("type") == "carousel" else "",
            "label_ia": "" if it.get("type") != "video" else ("oui" if it.get("ai_label", True) else "non"),
            "mur": "trop récent" if now - sent < MIN_AGE else "",
            "titre": (p["text"] or "").strip().split("\n")[0][:70],
            **{k: m.get(k, 0) for k in METRICS},
        })
    rows.sort(key=lambda r: (r["date"], r["heure"]), reverse=True)
    return rows


def avg(rows, key):
    return sum(r[key] for r in rows) / len(rows) if rows else 0


def compare(rows, field, title, network=None):
    sel = [r for r in rows if r[field] and not r["mur"] and (network is None or r["reseau"] == network)]
    groups = defaultdict(list)
    for r in sel:
        groups[r[field]].append(r)
    if len(groups) < 2:
        return f"### {title}\n\nPas encore assez de données (il faut 2 variantes avec des posts de plus de 36 h).\n"
    lines = [f"### {title}", "",
             "| Variante | Posts | Vues moy. | Réactions moy. | Partages moy. | Visionnage moy. (s) |",
             "|---|---|---|---|---|---|"]
    ranked = sorted(groups.items(), key=lambda kv: -avg(kv[1], "views"))
    for name, g in ranked:
        lines.append(f"| {name} | {len(g)} | {avg(g, 'views'):.0f} | {avg(g, 'reactions'):.1f} | "
                     f"{avg(g, 'shares'):.1f} | {avg(g, 'averageTimeWatched'):.1f} |")
    best, second = ranked[0], ranked[1]
    if min(len(best[1]), len(second[1])) >= 5:
        verdict = f"**Gagnant provisoire : {best[0]}**"
    else:
        verdict = f"Tendance : {best[0]} devant, mais moins de 5 posts par variante — attendre avant de conclure."
    return "\n".join(lines) + f"\n\n{verdict}\n"


def report(rows, now):
    ok = [r for r in rows if not r["mur"]]
    out = [f"# Tableau de bord des tests — {paris(now):%d/%m/%Y %H:%M}", "",
           f"{len(rows)} posts publiés relevés, {len(ok)} assez anciens (> 36 h) pour être comparés.", ""]
    for net in ("tiktok", "instagram"):
        sel = sorted([r for r in ok if r["reseau"] == net], key=lambda r: -r["views"])
        if not sel:
            continue
        out += [f"## {net.capitalize()} — top 5", "",
                "| Vues | Réac. | Partages | Format | Date | Titre |", "|---|---|---|---|---|---|"]
        out += [f"| {r['views']:.0f} | {r['reactions']:.0f} | {r['shares']:.0f} | {r['format']} | "
                f"{r['date']} {r['heure']} | {r['titre']} |" for r in sel[:5]]
        out += ["", f"Moyenne : {avg(sel, 'views'):.0f} vues par post, {avg(sel, 'reactions'):.1f} réactions.", ""]
    out += ["## Tests A/B", ""]
    out.append(compare(rows, "accroche", "Accroche v1 (définition) vs v2 (problème) vs v3 (valeur à enregistrer) — carrousels TikTok", "tiktok"))
    out.append(compare(rows, "accroche", "Accroche v1 vs v2 vs v3 — carrousels Instagram", "instagram"))
    out.append(compare(rows, "label_ia", "Label « contenu IA » oui / non — vidéos TikTok", "tiktok"))
    out.append(compare(rows, "label_ia", "Label « contenu IA » oui / non — Reels Instagram", "instagram"))
    out.append(compare([r for r in rows if r["reseau"] == "tiktok"], "creneau", "Créneaux horaires — TikTok"))
    out.append(compare(rows, "format", "Carrousel photo vs diaporama vidéo avec musique vs vidéo — TikTok", "tiktok"))
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    args = ap.parse_args()
    api_key = os.getenv("BUFFER_API_KEY")
    if not api_key:
        sys.exit("BUFFER_API_KEY manquante")
    planning = json.loads((ROOT / "planning.json").read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)
    try:
        posts = fetch(api_key, planning["organization_id"], now - timedelta(days=args.days))
    except BufferError as e:
        sys.exit(str(e))
    channels = {planning["channel_id"], planning.get("tiktok_channel_id")}
    rows = rows_from([p for p in posts if p["channelId"] in channels], planning, now)
    OUT.mkdir(exist_ok=True)
    with open(OUT / "posts.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["date"])
        w.writeheader()
        w.writerows(rows)
    (OUT / "RAPPORT.md").write_text(report(rows, now) + "\n", encoding="utf-8")
    print(f"{len(rows)} posts relevés -> stats/posts.csv, stats/RAPPORT.md")


if __name__ == "__main__":
    main()
