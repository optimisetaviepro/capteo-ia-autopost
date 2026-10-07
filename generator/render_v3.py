#!/usr/bin/env python3
"""Carrousels v3 (07/10/2026) : format « valeur à enregistrer » pour sortir du plancher des 250 vues.

Différences avec render.py (v1/v2) :
  - TikTok en 1080x1920 plein écran (media/t/NN), Instagram en 1080x1350 (media/c/NN) ;
  - couverture lime à fort contraste, mots surlignés, une promesse chiffrée ;
  - slides denses : outil réel (logo + capture du site), prompt à copier, ou texte ;
  - dernière slide = « partie 2 demain » / enregistre, pour déclencher abonnements et enregistrements ;
  - texte gardé dans la zone sûre TikTok (ni sous la légende en bas, ni sous les boutons à droite).

Contenu : contenu/v3/*.json, liste de carrousels :
  {"id": "70", "hook": "7 sites IA *gratuits* que personne ne connaît", "badge": "📌 Enregistre",
   "sub": "Le n°4 m'a fait gagner 2 h", "slides": [
      {"type": "tool", "name": "NotebookLM", "domain": "notebooklm.google.com",
       "what": "Tes PDF deviennent un podcast", "how": "…", "free": "Gratuit", "shot": true},
      {"type": "prompt", "title": "…", "prompt": "…", "tip": "…"},
      {"type": "text", "title": "…", "body": "…"}],
   "end": {"title": "Partie 2 demain", "body": "…"}, "caption": "…"}
  Les *mots entre astérisques* sont surlignés.

Usage :
    python generator/render_v3.py                 # rend tous les carrousels v3 absents de media/
    python generator/render_v3.py --only 70,71    # re-rend ceux-là
"""
import argparse
import base64
import html
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = ROOT / "contenu" / "v3"
MEDIA_DIR = ROOT / "media"
SHOTS_DIR = ROOT / "generator" / "cache" / "shots"
HANDLE = "@capteo_ia"
# Le TikTok s'appelle encore @cindy_mlm : pas de pseudo sur les slides TikTok tant qu'il n'est pas renommé
# (mettre TIKTOK_HANDLE = "@capteo_ia" puis re-rendre avec --only).
TIKTOK_HANDLE = "@capteo_ia"


def handle(fmt):
    return TIKTOK_HANDLE if fmt == "tiktok" else HANDLE

FONTS = ("https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700;800;900"
         "&family=JetBrains+Mono:wght@500;700&family=Noto+Color+Emoji&display=swap")

CSS = """
:root { --ink:#0e0f12; --lime:#c8f03c; --paper:#f6f4ee; --mute:#6d6b66; }
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:'Archivo', 'Noto Color Emoji', sans-serif; -webkit-font-smoothing:antialiased; }
.mono { font-family:'JetBrains Mono', 'Noto Color Emoji', monospace; }
.f { position:relative; width:1080px; overflow:hidden; }
mark { background:var(--ink); color:var(--lime); padding:0 .14em; border-radius:.12em;
       -webkit-box-decoration-break:clone; box-decoration-break:clone; }
.paper mark { background:var(--lime); color:var(--ink); }
.handle { font-size:30px; font-weight:700; letter-spacing:.02em; }
.num { font-size:30px; font-weight:700; }
.badge { display:inline-block; font-size:34px; font-weight:800; padding:14px 26px; border-radius:999px; }
.box { background:#fff; border:3px solid var(--ink); border-radius:28px; }
.chip { display:inline-block; font-size:28px; font-weight:800; padding:8px 20px; border-radius:999px;
        background:var(--lime); color:var(--ink); white-space:nowrap; border:3px solid var(--ink); }
"""


def esc(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"\*(.+?)\*", r"<mark>\1</mark>", s)
    return s.replace("\n", "<br>")


def page(body):
    return (f'<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="{FONTS}">'
            f'<style>{CSS}</style></head><body>{body}</body></html>')


def geometry(fmt):
    """Zone utile : TikTok masque ~380 px en bas (légende) et ~150 px à droite (boutons)."""
    if fmt == "tiktok":
        return {"h": 1920, "top": 200, "bottom": 470, "left": 80, "right": 170}
    return {"h": 1350, "top": 90, "bottom": 110, "left": 84, "right": 84}


def hook_size(text, fmt):
    n = len(text.replace("*", ""))
    big = fmt == "tiktok"
    if n <= 30:
        return 132 if big else 118
    if n <= 50:
        return 116 if big else 100
    if n <= 70:
        return 100 if big else 86
    return 88 if big else 76


def cover(c, fmt, total):
    g = geometry(fmt)
    tt = fmt == "tiktok"
    sub = (f'<div style="font-size:{46 if tt else 40}px;font-weight:600;margin-top:48px;line-height:1.25">'
           f'{esc(c["sub"])}</div>') if c.get("sub") else ""
    emoji = (f'<div style="font-size:{150 if tt else 120}px;line-height:1;margin-bottom:40px">{c["emoji"]}</div>'
             if c.get("emoji") else "")
    return f"""<div class="f" style="height:{g['h']}px;background:var(--lime);color:var(--ink)">
  <div style="position:absolute;top:{g['top']}px;left:{g['left']}px;right:{g['right']}px;display:flex;justify-content:space-between">
    <span class="handle">{handle(fmt)}</span><span class="num mono">1/{total}</span></div>
  <div style="position:absolute;left:{g['left']}px;right:{g['right']}px;top:{g['top']}px;bottom:{g['bottom']}px;
       display:flex;flex-direction:column;justify-content:center">
    {emoji}
    <div style="font-size:{hook_size(c['hook'], fmt)}px;font-weight:900;line-height:1.02;letter-spacing:-0.035em">{esc(c['hook'])}</div>
    {sub}
    <div style="margin-top:56px"><span class="badge" style="background:var(--ink);color:var(--lime)">{esc(c.get('badge', 'Swipe →'))}</span></div>
  </div>
</div>"""


def frame(fmt, i, total, inner, dark=False):
    g = geometry(fmt)
    bg, fg, cls = ("var(--ink)", "#fff", "") if dark else ("var(--paper)", "var(--ink)", "paper")
    return f"""<div class="f {cls}" style="height:{g['h']}px;background:{bg};color:{fg}">
  <div style="position:absolute;top:{g['top']}px;left:{g['left']}px;right:{g['right']}px;display:flex;justify-content:space-between;opacity:.7">
    <span class="handle">{handle(fmt)}</span><span class="num mono">{i}/{total}</span></div>
  <div style="position:absolute;left:{g['left']}px;right:{g['right']}px;top:{g['top'] + 70}px;bottom:{g['bottom']}px;
       display:flex;flex-direction:column;justify-content:center">{inner}</div>
</div>"""


def tool_slide(s, idx, fmt, shot_b64):
    tt = fmt == "tiktok"
    sz = 96 if tt else 80
    logo = (f'<img src="https://www.google.com/s2/favicons?domain={s["domain"]}&sz=128" '
            f'style="width:{sz}px;height:{sz}px;border-radius:20px;background:#fff;border:3px solid var(--ink);padding:10px">')
    shot = ""
    if shot_b64:
        dots = "".join(f'<i style="width:14px;height:14px;border-radius:9px;background:{c}"></i>'
                       for c in ("#ff5f57", "#febc2e", "#28c840"))
        shot = (f'<div class="box" style="margin-top:40px;overflow:hidden">'
                f'<div style="height:44px;border-bottom:3px solid var(--ink);display:flex;align-items:center;gap:12px;padding:0 20px">'
                f'{dots}<span class="mono" style="font-size:22px;margin-left:14px;color:var(--mute)">{html.escape(s["domain"])}</span></div>'
                f'<img src="data:image/jpeg;base64,{shot_b64}" style="display:block;width:100%;height:{500 if tt else 300}px;'
                f'object-fit:cover;object-position:top"></div>')
    free = f'<div style="margin-top:28px"><span class="chip">{esc(s["free"])}</span></div>' if s.get("free") else ""
    how = (f'<div style="font-size:{38 if tt else 31}px;line-height:1.35;margin-top:24px;color:#33322f">{esc(s["how"])}</div>'
           if s.get("how") else "")
    return f"""
    <div style="display:flex;align-items:center;gap:26px">
      <span class="mono" style="font-size:{64 if tt else 54}px;font-weight:700">{idx:02d}</span>{logo}
      <div><div style="font-size:{62 if tt else 52}px;font-weight:900;letter-spacing:-0.02em;line-height:1">{esc(s['name'])}</div>
      <div class="mono" style="font-size:24px;color:var(--mute);margin-top:10px">{html.escape(s['domain'])}</div></div>
    </div>
    <div style="font-size:{56 if tt else 44}px;font-weight:800;line-height:1.1;letter-spacing:-0.02em;margin-top:40px">{esc(s['what'])}</div>
    {how}{free}{shot}"""


def prompt_slide(s, fmt):
    tt = fmt == "tiktok"
    n = len(s["prompt"])
    psize = (40 if n < 160 else 35 if n < 260 else 31) if tt else (34 if n < 160 else 30 if n < 260 else 26)
    tip = (f'<div style="font-size:{34 if tt else 29}px;margin-top:30px;line-height:1.35;color:#33322f">💡 {esc(s["tip"])}</div>'
           if s.get("tip") else "")
    return f"""
    <div style="font-size:{60 if tt else 50}px;font-weight:900;letter-spacing:-0.025em;line-height:1.05">{esc(s['title'])}</div>
    <div class="box" style="margin-top:40px;padding:38px 40px 40px">
      <div class="mono" style="font-size:24px;font-weight:700;color:var(--mute);margin-bottom:20px">PROMPT À COPIER ↓</div>
      <div class="mono" style="font-size:{psize}px;line-height:1.42;font-weight:500">{esc(s['prompt'])}</div>
    </div>{tip}"""


def text_slide(s, fmt):
    tt = fmt == "tiktok"
    return f"""
    <div style="font-size:{76 if tt else 62}px;font-weight:900;letter-spacing:-0.03em;line-height:1.04">{esc(s['title'])}</div>
    <div style="width:110px;height:14px;background:var(--lime);margin:44px 0 40px;border:3px solid var(--ink)"></div>
    <div style="font-size:{44 if tt else 36}px;line-height:1.38;font-weight:500">{esc(s['body'])}</div>"""


def end_slide(c, fmt):
    tt = fmt == "tiktok"
    e = c["end"]
    return f"""
    <div style="font-size:{108 if tt else 90}px;line-height:1">{e.get('emoji', '📌')}</div>
    <div style="font-size:{92 if tt else 76}px;font-weight:900;letter-spacing:-0.035em;line-height:1.02;margin-top:36px">{esc(e['title'])}</div>
    <div style="font-size:{44 if tt else 36}px;line-height:1.35;margin-top:36px;color:#d9d7d0">{esc(e['body'])}</div>
    <div style="margin-top:56px"><span class="badge" style="background:var(--lime);color:var(--ink)">{"Abonne-toi à " + handle(fmt) if handle(fmt) else "➕ Abonne-toi pour la suite"}</span></div>"""


def site_shot(ctx, domain):
    """Capture mise en cache de la page d'accueil ; tente de fermer la bannière cookies."""
    out = SHOTS_DIR / f"{domain.replace('/', '_')}.jpg"
    if out.is_file():
        return out
    SHOTS_DIR.mkdir(parents=True, exist_ok=True)
    pg = ctx.new_page()
    try:
        pg.goto(f"https://{domain}", wait_until="domcontentloaded", timeout=30000)
        pg.wait_for_timeout(4500)
        try:
            b = pg.get_by_role("button", name=re.compile(
                r"^(decline all|reject all|tout refuser|refuser tout|rejeter tout|decline|refuser)", re.I))
            if b.count():
                b.first.click(timeout=2000)
                pg.wait_for_timeout(800)
        except Exception:
            pass
        # Retire les bannières cookies / consentement : tout bloc fixe ou collant qui parle de cookies.
        pg.evaluate("""() => {
          for (const el of document.querySelectorAll('body *')) {
            const st = getComputedStyle(el);
            if ((st.position === 'fixed' || st.position === 'sticky') &&
                /cookie|consent|confidentialit/i.test(el.innerText || '') && el.innerText.length < 1500) el.remove();
          }
          document.documentElement.style.overflow = 'auto'; document.body.style.overflow = 'auto';
        }""")
        pg.wait_for_timeout(500)
        pg.screenshot(path=str(out), type="jpeg", quality=82)
        return out
    except Exception as e:
        print(f"    capture impossible pour {domain} : {e.__class__.__name__}")
        return None
    finally:
        pg.close()


def shoot(pg, body, out, height):
    pg.set_viewport_size({"width": 1080, "height": height})
    pg.set_content(page(body), wait_until="networkidle")
    pg.evaluate("document.fonts.ready")
    out.parent.mkdir(parents=True, exist_ok=True)
    pg.screenshot(path=str(out), clip={"x": 0, "y": 0, "width": 1080, "height": height})


def render(pg, ctx, c):
    total = len(c["slides"]) + 2
    shots = {}
    for s in c["slides"]:
        if s["type"] == "tool" and s.get("shot"):
            f = site_shot(ctx, s["domain"])
            shots[s["domain"]] = base64.b64encode(f.read_bytes()).decode() if f else None
    for fmt, folder in (("tiktok", "t"), ("instagram", "c")):
        h = geometry(fmt)["h"]
        out = MEDIA_DIR / folder / c["id"]
        for old in out.glob("*.png"):
            old.unlink()
        shoot(pg, cover(c, fmt, total), out / "1.png", h)
        n_tool = 0
        for i, s in enumerate(c["slides"], 2):
            if s["type"] == "tool":
                n_tool += 1
                inner = tool_slide(s, n_tool, fmt, shots.get(s["domain"]))
            elif s["type"] == "prompt":
                inner = prompt_slide(s, fmt)
            else:
                inner = text_slide(s, fmt)
            shoot(pg, frame(fmt, i, total, inner), out / f"{i}.png", h)
        shoot(pg, frame(fmt, total, total, end_slide(c, fmt), dark=True), out / f"{total}.png", h)


def load_all():
    items = []
    for f in sorted(CONTENT_DIR.glob("*.json")):
        items += json.loads(f.read_text(encoding="utf-8"))
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="ids à (re)rendre, séparés par des virgules")
    args = ap.parse_args()
    items = load_all()
    if args.only:
        wanted = set(args.only.split(","))
        items = [c for c in items if c["id"] in wanted]
    else:
        items = [c for c in items if not (MEDIA_DIR / "t" / c["id"] / "1.png").is_file()]
    if not items:
        print("Rien à rendre.")
        return
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1280, "height": 800}, locale="fr-FR",
                                  user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                              "(KHTML, like Gecko) Chrome/129.0 Safari/537.36"))
        pg = browser.new_page()
        for c in items:
            render(pg, ctx, c)
            print(f"  v3 {c['id']} : {c['hook'].replace('*', '')[:60]}")
        browser.close()


if __name__ == "__main__":
    main()
