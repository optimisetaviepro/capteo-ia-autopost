#!/usr/bin/env python3
"""Ajoute au planning les vidéos de la série « Claude Reactions » : 2 par jour (12:30 et 20:00, heure de Paris).

    python scripts/add_videos.py --start 2026-10-04 [--dry-run]

Lit les légendes dans PUBLICATION.md du projet claude-reactions, prend les vidéos déjà copiées
dans media/v/ (NN-slug.mp4 + NN-slug.jpg) dans l'ordre ORDER, et n'ajoute que celles qui ne sont
pas encore au planning. Gère le passage à l'heure d'hiver (+01:00 à partir du 25/10/2026).
"""
import argparse
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLICATION = Path(r"C:\Users\enzof\prospection-immo\claude-reactions\PUBLICATION.md")
SLOTS = ["12:30", "20:00"]
# Les plus fortes d'abord ; les variantes d'accroche (b) une fois la série publiée, pour comparer.
ORDER = ["06-forma", "13-nexa", "08-spark", "01-nova", "20-bloom", "15-orbital", "11-volta", "07-aura", "02-orbit", "21-chrono",
         "03-pulse", "24-prism", "04-terra", "14-stack", "12-synth", "19-vandal", "09-flux", "23-nomad", "05-lento", "17-vault",
         "18-pixel", "22-tide", "10-habitat", "16-flow", "25-solaris", "26-echo", "27-kino", "28-folio", "29-alize", "30-verde",
         "13b-nexa", "06b-forma", "08b-spark", "01b-nova", "15b-orbital"]
VARIANT_HOOKS = {"01b": "Ces écouteurs n'existent pas.", "06b": "Ce clip a demandé 0 heure de montage.",
                 "08b": "4 000 particules. Toutes codées par une IA.", "13b": "Ce téléphone n'existe pas.", "15b": "Aucune fusée n'a été filmée."}


def captions():
    text = PUBLICATION.read_text(encoding="utf-8")
    out = {}
    for m in re.finditer(r"### (\d+) — [^\n]+\n\*\*Accroche :\*\* ([^\n]+)\n\*\*Légende :\*\* ([^\n]+)\n`([^`]+)`", text):
        out[m.group(1)] = {"hook": m.group(2).strip(), "body": m.group(3).strip(), "tags": m.group(4).strip()}
    return out


def caption_for(slug, caps):
    num = re.match(r"\d+", slug).group(0)
    c = caps.get(num)
    if not c:
        return None
    variant = re.match(r"(\d+b)-", slug)
    hook = VARIANT_HOOKS[variant.group(1)] if variant else c["hook"]
    return (f"{hook}\n\n{c['body']}\n\n"
            "Marque fictive. Pub 100 % codée par Claude, sans logiciel de montage.\n"
            "👉 Note-la sur 10 en commentaire.\n\n"
            f"{c['tags']}")


def offset(d):
    # Heure d'été jusqu'au samedi 24/10/2026 inclus, heure d'hiver ensuite.
    return "+02:00" if d < date(2026, 10, 25) else "+01:00"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, help="premier jour (AAAA-MM-JJ)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    planning_path = ROOT / "planning.json"
    planning = json.loads(planning_path.read_text(encoding="utf-8"))
    already = {it["media"] for it in planning["items"] if it["type"] == "video"}
    caps = captions()
    todo = [s for s in ORDER if (ROOT / "media" / "v" / f"{s}.mp4").is_file() and f"v/{s}.mp4" not in already]
    missing = [s for s in ORDER if not (ROOT / "media" / "v" / f"{s}.mp4").is_file()]

    # Premier créneau libre : à partir de --start, après la dernière vidéo déjà planifiée.
    taken = {it["at"] for it in planning["items"] if it["type"] == "video"}
    last = max((datetime.fromisoformat(a) for a in taken), default=None)
    d, new = date.fromisoformat(args.start), []
    while len(new) < len(todo):
        for slot in SLOTS:
            if len(new) == len(todo):
                break
            at = f"{d.isoformat()}T{slot}:00{offset(d)}"
            if at in taken or (last and datetime.fromisoformat(at) <= last) or datetime.fromisoformat(at) <= datetime.now().astimezone():
                continue
            slug = todo[len(new)]
            text = caption_for(slug, caps)
            if not text:
                raise SystemExit(f"légende introuvable pour {slug} dans PUBLICATION.md")
            new.append({"at": at, "type": "video", "media": f"v/{slug}.mp4", "text": text})
        d += timedelta(days=1)

    for it in new:
        print(f"  {it['at']}  {it['media']:24}  {it['text'].splitlines()[0]}")
    print(f"{len(new)} vidéo(s) ajoutée(s)" + (f" — pas encore exportées : {', '.join(missing)}" if missing else ""))
    if not args.dry_run and new:
        planning["items"] = sorted(planning["items"] + new, key=lambda it: datetime.fromisoformat(it["at"]))
        planning_path.write_text(json.dumps(planning, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
