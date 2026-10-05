#!/usr/bin/env python3
"""Vidéos TikTok du compte giletjaune2.0 : photo IA + message + compte à rebours vers le 17 octobre.

TikTok refuse le label « contenu IA » sur les posts photo via l'API : chaque post est donc une vidéo
9:16 de 12 s (media/gj/v/NN.mp4) montée à partir de 3 slides 1080x1340 :
  1. la photo (générée par IA, déjà marquée « Image IA »)
  2. le message du post
  3. « J-X avant le 17 octobre » + appel à partager (« C'est aujourd'hui » le jour J)
Musique de fond : contenu/giletjaune/music/m1-4.wav (générée par claude-reactions/tools/music.py, libre de droits).
Puis ajoute les posts à planning.json (compte secondaire "giletjaune", label IA TikTok obligatoire).

Usage :
    python generator/giletjaune.py            # rend tout + met à jour le planning
    python generator/giletjaune.py --no-plan  # rend seulement
"""
import argparse
import html
import json
import subprocess
from datetime import date, datetime
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SRC = Path(r"D:\ONEDRIVE\Bureau\MES CRÉATIONS IA\images gilet jaune")
POSTS = ROOT / "contenu" / "giletjaune" / "posts.json"
OUT = ROOT / "media" / "gj"
MUSIC = ROOT / "contenu" / "giletjaune" / "music"
W, H = 1080, 1340
D_DAY = date(2026, 10, 17)

FONTS = "https://fonts.googleapis.com/css2?family=Anton&family=Inter:wght@500;700&display=swap"
CSS = """
* { margin:0; padding:0; box-sizing:border-box; }
body { width:1080px; height:1340px; background:#0d0d0d; color:#fff; font-family:'Inter', sans-serif;
       position:relative; overflow:hidden; }
.band { position:absolute; left:0; right:0; height:28px;
        background:repeating-linear-gradient(-45deg,#ffd400 0 40px,#0d0d0d 40px 80px); }
.top { position:absolute; top:110px; left:90px; right:90px; font-family:'Anton', sans-serif; font-size:64px;
       color:#ffd400; letter-spacing:.02em; }
.mid { position:absolute; left:90px; right:90px; top:50%; transform:translateY(-50%); }
.msg { font-family:'Anton', sans-serif; font-size:108px; line-height:1.05; text-transform:uppercase; }
.msg.long { font-size:90px; }
.big { font-family:'Anton', sans-serif; font-size:330px; line-height:.9; color:#ffd400; }
.sub { font-family:'Anton', sans-serif; font-size:78px; text-transform:uppercase; margin-top:20px; }
.foot { position:absolute; bottom:110px; left:90px; right:90px; font-size:38px; font-weight:700; line-height:1.4; }
.foot span { color:#ffd400; }
.note { position:absolute; bottom:56px; right:90px; font-size:22px; color:#8a8a8a; }
"""


def page(body):
    return (f'<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="{FONTS}">'
            f'<style>{CSS}</style></head><body><div class="band" style="top:0"></div>{body}'
            f'<div class="band" style="bottom:0"></div></body></html>')


def message_slide(msg):
    cls = "msg long" if len(msg) > 60 else "msg"
    return page(f'<div class="top">LE 17 OCTOBRE</div><div class="mid"><div class="{cls}">{html.escape(msg)}</div></div>'
                f'<div class="foot">Mobilisation <span>pacifique</span>.</div><div class="note">Image précédente générée par IA</div>')


def countdown_slide(d):
    left = (D_DAY - d).days
    if left == 0:
        head = '<div class="big" style="font-size:180px">C\'EST<br>AUJOURD\'HUI</div>'
    else:
        head = f'<div class="big">J-{left}</div><div class="sub">avant le 17 octobre</div>'
    return page(f'<div class="mid">{head}</div><div class="foot">Partage à <span>3 personnes</span> qui en ont marre.<br>'
                f'Ta ville sera là ? <span>Dis-le en commentaire.</span></div>')


def caption(p):
    return (f"{p['message']}\n\n"
            "Le 17 octobre, on se retrouve. Pacifiquement. 💛\n\n"
            "👉 Partage à 3 personnes qui en ont marre.\n"
            "💬 Ta ville sera là ? Dis-le en commentaire.\n\n"
            "Images générées par IA.\n\n"
            "#giletsjaunes #17octobre #pouvoirdachat #france #mobilisation")


def shoot(pg, content, out):
    pg.set_content(content, wait_until="networkidle")
    pg.evaluate("document.fonts.ready")
    pg.screenshot(path=str(out), clip={"x": 0, "y": 0, "width": W, "height": H})


def make_video(d, out, music):
    """Photo (zoom lent sur fond flouté) 5 s -> message 4 s -> compte à rebours 4,5 s, fondus de 0,4 s."""
    fmt = "fps=30,format=yuv420p,setsar=1"
    graph = (
        f"[0]split[a][b];"
        f"[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=40:4,eq=brightness=-0.18[bg];"
        f"[b]scale=w='1080*(1+0.05*t/5)':h=-1:eval=frame,crop=1080:1340[fg];"
        f"[bg][fg]overlay=0:290,{fmt}[v0];"
        f"[1]pad=1080:1920:0:290:color=0x0d0d0d,{fmt}[v1];"
        f"[2]pad=1080:1920:0:290:color=0x0d0d0d,{fmt}[v2];"
        f"[v0][v1]xfade=transition=fade:duration=0.4:offset=4.6[x1];"
        f"[x1][v2]xfade=transition=fade:duration=0.4:offset=8.2[v];"
        f"[3:a]afade=t=out:st=11.7:d=1,volume=0.8[aud]"
    )
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-loop", "1", "-t", "5", "-i", str(d / "1.png"),
           "-loop", "1", "-t", "4", "-i", str(d / "2.png"),
           "-loop", "1", "-t", "4.5", "-i", str(d / "3.png"),
           "-i", str(music), "-filter_complex", graph, "-map", "[v]", "-map", "[aud]",
           "-t", "12.7", "-c:v", "libx264", "-preset", "medium", "-crf", "22", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-plan", action="store_true")
    args = ap.parse_args()
    posts = json.loads(POSTS.read_text(encoding="utf-8"))

    with sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_page(viewport={"width": W, "height": H})
        for post in posts:
            d = OUT / post["id"]
            d.mkdir(parents=True, exist_ok=True)
            Image.open(SRC / post["image"]).convert("RGB").resize((W, H), Image.LANCZOS).save(d / "1.png", optimize=True)
            shoot(pg, message_slide(post["message"]), d / "2.png")
            shoot(pg, countdown_slide(date.fromisoformat(post["date"])), d / "3.png")
            (OUT / "v").mkdir(exist_ok=True)
            make_video(d, OUT / "v" / f"{post['id']}.mp4", MUSIC / f"m{int(post['id']) % 4 + 1}.wav")
            print(f"  gj/{post['id']} : {post['date']} {post['slot']} — {post['message'][:50]}")
        browser.close()

    if args.no_plan:
        return
    planning = json.loads((ROOT / "planning.json").read_text(encoding="utf-8"))
    planning["items"] = [it for it in planning["items"] if it.get("account") != "giletjaune"]
    for post in posts:
        planning["items"].append({
            "at": f"{post['date']}T{post['slot']}:00+02:00", "type": "video", "media": f"gj/v/{post['id']}.mp4",
            "text": caption(post), "account": "giletjaune", "ai_label": True, "cover_ms": 1500,
        })
    planning["items"].sort(key=lambda it: datetime.fromisoformat(it["at"]))
    (ROOT / "planning.json").write_text(json.dumps(planning, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(posts)} posts ajoutés au planning (compte giletjaune)")


if __name__ == "__main__":
    main()
