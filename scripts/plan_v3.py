#!/usr/bin/env python3
"""Bascule le planning sur les carrousels v3 (07/10/2026).

À partir de --start, sur le compte principal (pas les comptes "account") :
  - retire les carrousels v1/v2 et les stories encore prévus ;
  - TikTok : 2 carrousels v3 par jour (12:15 et 18:30, media/t/NN en 1080x1920)
    + la vidéo de 20:00 ; la vidéo de 12:30 ne part plus que sur Instagram ;
  - Instagram : le carrousel v3 de 18:30 (media/c/NN en 1080x1350) + les Reels déjà prévus.
TikTok passe ainsi de 5 à 3 posts par jour : moins de posts faibles, plus de posts à garder.

Usage :
    python scripts/plan_v3.py --start 2026-10-08 [--dry-run]
"""
import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "generator"))
from render import at  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

# Ordre de passage : (créneau 12:15, créneau 18:30) jour après jour.
# La série « IA gratuites » (70, 72-76) occupe 18:30 six jours de suite : chaque partie annonce la suivante.
# 71 annonce « demain : le prompt qui écrit tes mails » → 82 le lendemain.
MIDI = ["77", "71", "82", "78", "81", "83", "86", "85", "80", "89", "84", "92", "95", "93", "91", "100"]
SOIR = ["70", "72", "73", "74", "75", "76", "87", "88", "79", "90", "94", "96", "97", "98", "99"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    start = date.fromisoformat(args.start)

    planning = json.loads((ROOT / "planning.json").read_text(encoding="utf-8"))
    content = {}
    for f in sorted((ROOT / "contenu" / "v3").glob("*.json")):
        content.update({c["id"]: c for c in json.loads(f.read_text(encoding="utf-8"))})
    for cid in MIDI + SOIR:
        for folder in ("t", "c"):
            if not (ROOT / "media" / folder / cid / "1.png").is_file():
                sys.exit(f"media/{folder}/{cid} manquant : lancer generator/render_v3.py")

    def future_main(it):
        return "account" not in it and datetime.fromisoformat(it["at"]).date() >= start

    kept, removed = [], 0
    for it in planning["items"]:
        if future_main(it) and it["type"] in ("carousel", "story"):
            removed += 1
            continue
        if future_main(it) and it["type"] == "video" and it["at"][11:16] == "12:30":
            it["networks"] = ["instagram"]
        kept.append(it)

    added = []
    for k in range(max(len(MIDI), len(SOIR))):
        day = start + timedelta(days=k)
        if k < len(MIDI):
            c = content[MIDI[k]]
            added.append({"at": at(day, "12:15"), "type": "carousel", "media": f"t/{c['id']}",
                          "text": c["caption"], "hook": "v3", "networks": ["tiktok"]})
        if k < len(SOIR):
            c = content[SOIR[k]]
            added.append({"at": at(day, "18:30"), "type": "carousel", "media": f"t/{c['id']}",
                          "text": c["caption"], "hook": "v3", "networks": ["tiktok"]})
            added.append({"at": at(day, "18:30"), "type": "carousel", "media": f"c/{c['id']}",
                          "text": c["caption"], "hook": "v3", "networks": ["instagram"]})

    planning["items"] = sorted(kept + added, key=lambda it: datetime.fromisoformat(it["at"]))
    print(f"{removed} anciens carrousels/stories retirés, {len(added)} posts v3 ajoutés "
          f"du {start:%d/%m} au {start + timedelta(days=max(len(MIDI), len(SOIR)) - 1):%d/%m}.")
    if not args.dry_run:
        (ROOT / "planning.json").write_text(json.dumps(planning, ensure_ascii=False, indent=2) + "\n",
                                            encoding="utf-8")


if __name__ == "__main__":
    main()
