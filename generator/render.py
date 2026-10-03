#!/usr/bin/env python3
"""Génère les carrousels (1080x1350) et les stories (1080x1920) au style @Capteo_IA,
puis les ajoute à planning.json.

Usage :
    python generator/render.py --start 2026-10-09        # rend tout contenu/*.json + planifie à partir du 9/10
    python generator/render.py --only 24,25 --no-plan    # re-rend quelques carrousels sans toucher au planning

Chaque jour : 3 carrousels (16:00, 16:45, 17:30) puis une story récap (18:00), heure de Paris.
Nécessite : pip install playwright && playwright install chromium (+ connexion pour Google Fonts).
"""
import argparse
import base64
import html
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = ROOT / "contenu"
MEDIA_DIR = ROOT / "media"
SLOTS = ["16:00", "16:45", "17:30"]
STORY_SLOT = "18:00"

FONTS = ("https://fonts.googleapis.com/css2?family=Schibsted+Grotesk:wght@400;500;600;700"
         "&family=JetBrains+Mono:wght@400;500&display=swap")

BASE_CSS = """
:root { --bg:#101114; --lime:#c8f03c; --cream:#f3f1ea; --body:#d6d3ca; --mute:#9a9893; }
* { margin:0; padding:0; box-sizing:border-box; }
html, body { background:var(--bg); }
body { font-family:'Schibsted Grotesk', sans-serif; color:var(--cream); -webkit-font-smoothing:antialiased; }
.mono { font-family:'JetBrains Mono', monospace; }
.frame { position:relative; width:1080px; padding:0 96px; overflow:hidden; background:var(--bg); }
.top { position:absolute; top:96px; left:96px; right:96px; display:flex; justify-content:space-between;
       font-size:26px; color:var(--mute); letter-spacing:.02em; }
.bottom { position:absolute; bottom:96px; left:96px; right:96px; display:flex; justify-content:space-between;
          align-items:center; font-size:28px; letter-spacing:.04em; }
.bottom .short { color:var(--mute); }
.bottom .go { color:var(--lime); display:flex; align-items:center; gap:18px; }
.mid { position:absolute; left:96px; right:96px; top:50%; transform:translateY(-50%); }
.kicker { color:var(--lime); font-size:30px; letter-spacing:.14em; text-transform:uppercase; margin-bottom:44px; }
.title { font-weight:600; letter-spacing:-0.015em; line-height:1.06; }
.bar { width:120px; height:8px; background:var(--lime); margin:52px 0 50px; }
.body { font-size:38px; line-height:1.45; color:var(--body); font-weight:400; }
"""

ARROW = ('<svg width="34" height="28" viewBox="0 0 34 28" fill="none" stroke="#c8f03c" stroke-width="3.4" '
         'stroke-linecap="round" stroke-linejoin="round"><path d="M2 14h29M19 2l12 12-12 12"/></svg>')


def esc(s):
    return html.escape(s, quote=False).replace("\n", "<br>")


def title_size(text, cover):
    n = len(text)
    if cover:
        return 100 if n <= 34 else 88 if n <= 52 else 76
    return 76 if n <= 34 else 66 if n <= 60 else 58


def slide_html(c, i, total, kind, k, t, b):
    footer = ('<span class="go mono">Enregistre &amp; partage</span>' if kind == "cta"
              else f'<span class="go mono">Swipe {ARROW}</span>')
    return f"""<div class="frame" style="height:1350px">
  <div class="top mono"><span>@Capteo_IA</span><span>{i:02d} / {total:02d}</span></div>
  <div class="mid">
    <div class="kicker mono">{esc(k)}</div>
    <div class="title" style="font-size:{title_size(t, kind == 'cover')}px">{esc(t)}</div>
    <div class="bar"></div>
    <div class="body">{esc(b)}</div>
  </div>
  <div class="bottom mono"><span class="short">{esc(c['short'])}</span>{footer}</div>
</div>"""


def story_html(day_items, covers_b64):
    n = len(day_items)
    word = {1: "Un nouveau post vient", 2: "2 nouveaux posts viennent", 3: "3 nouveaux posts viennent"}[n]
    cards = "".join(
        f'<img src="data:image/png;base64,{b}" style="width:276px;height:345px;border:2px solid #2a2c31;'
        f'border-radius:16px;display:block">' for b in covers_b64)
    lines = "".join(f'<div>{c["id"]} — {esc(c["short"])}</div>' for c in day_items)
    return f"""<div class="frame" style="height:1920px">
  <div style="position:absolute;top:262px;left:96px;right:96px">
    <div class="mono" style="color:var(--lime);font-size:36px;letter-spacing:.1em">@CAPTEO_IA · NOUVEAU</div>
    <div class="title" style="font-size:112px;margin-top:36px;line-height:1.04">{word} de tomber.</div>
    <div style="width:140px;height:10px;background:var(--lime);margin:52px 0 92px"></div>
    <div style="display:flex;gap:30px">{cards}</div>
    <div class="mono" style="margin-top:72px;font-size:32px;line-height:1.7;color:var(--body);letter-spacing:.02em">{lines}</div>
  </div>
  <div style="position:absolute;left:96px;right:96px;bottom:250px;height:146px;background:var(--lime);border-radius:24px;
       display:flex;align-items:center;justify-content:space-between;padding:0 56px;color:#101114">
    <span style="font-size:54px;font-weight:700;letter-spacing:-0.01em">Va voir mon profil</span>
    <svg width="48" height="40" viewBox="0 0 34 28" fill="none" stroke="#101114" stroke-width="3.6"
      stroke-linecap="round" stroke-linejoin="round"><path d="M2 14h29M19 2l12 12-12 12"/></svg>
  </div>
</div>"""


def page(body):
    return (f'<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="{FONTS}">'
            f'<style>{BASE_CSS}</style></head><body>{body}</body></html>')


def shoot(pg, body, out, height):
    pg.set_viewport_size({"width": 1080, "height": height})
    pg.set_content(page(body), wait_until="networkidle")
    pg.evaluate("document.fonts.ready")
    out.parent.mkdir(parents=True, exist_ok=True)
    pg.screenshot(path=str(out), clip={"x": 0, "y": 0, "width": 1080, "height": height})


def render_carousel(pg, c):
    slides = [("cover", c["kicker"], c["title"], c["subtitle"])]
    slides += [("slide", s["k"], s["t"], s["b"]) for s in c["slides"]]
    slides.append(("cta", c["cta"]["k"], c["cta"]["t"], c["cta"]["b"]))
    for i, (kind, k, t, b) in enumerate(slides, 1):
        shoot(pg, slide_html(c, i, len(slides), kind, k, t, b), MEDIA_DIR / "c" / c["id"] / f"{i}.png", 1350)


def paris_offset(d):
    """+02:00 en heure d'été (dernier dim. de mars → dernier dim. d'octobre), sinon +01:00."""
    def last_sunday(year, month):
        nxt = date(year + (month == 12), month % 12 + 1, 1)
        x = nxt - timedelta(days=1)
        return x - timedelta(days=(x.weekday() + 1) % 7)
    summer = last_sunday(d.year, 3) <= d < last_sunday(d.year, 10)
    return timezone(timedelta(hours=2 if summer else 1))


def at(d, hhmm):
    h, m = map(int, hhmm.split(":"))
    return datetime(d.year, d.month, d.day, h, m, tzinfo=paris_offset(d)).isoformat()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", help="premier jour à planifier (AAAA-MM-JJ)")
    ap.add_argument("--only", help="ids à (re)rendre, séparés par des virgules")
    ap.add_argument("--no-plan", action="store_true", help="ne modifie pas planning.json")
    args = ap.parse_args()

    carousels = []
    for f in sorted(CONTENT_DIR.glob("*.json")):
        carousels += json.loads(f.read_text(encoding="utf-8"))
    if args.only:
        wanted = set(args.only.split(","))
        carousels = [c for c in carousels if c["id"] in wanted]

    planning = json.loads((ROOT / "planning.json").read_text(encoding="utf-8"))
    planned = {it["media"] for it in planning["items"]}
    todo = carousels if args.no_plan else [c for c in carousels if f"c/{c['id']}" not in planned]
    if not todo:
        print("Rien de nouveau à générer.")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_page()
        for c in todo:
            render_carousel(pg, c)
            print(f"  carrousel {c['id']} : {c['short']}")

        if not args.no_plan:
            if not args.start:
                raise SystemExit("--start est obligatoire pour planifier")
            day = date.fromisoformat(args.start)
            for k in range(0, len(todo), len(SLOTS)):
                batch = todo[k:k + len(SLOTS)]
                for c, slot in zip(batch, SLOTS):
                    planning["items"].append({"at": at(day, slot), "type": "carousel",
                                              "media": f"c/{c['id']}", "text": c["caption"]})
                covers = [base64.b64encode((MEDIA_DIR / "c" / c["id"] / "1.png").read_bytes()).decode()
                          for c in batch]
                story = f"story_jour{day:%d}_{day:%m}.png"
                shoot(pg, story_html(batch, covers), MEDIA_DIR / "s" / story, 1920)
                planning["items"].append({"at": at(day, STORY_SLOT), "type": "story",
                                          "media": f"s/{story}", "text": ""})
                print(f"  {day:%d/%m} : {', '.join(c['id'] for c in batch)} + story")
                day += timedelta(days=1)
            planning["items"].sort(key=lambda it: datetime.fromisoformat(it["at"]))
            (ROOT / "planning.json").write_text(
                json.dumps(planning, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        browser.close()


if __name__ == "__main__":
    main()
