#!/usr/bin/env python3
"""Diaporama vidéo d'un carrousel v3 (test A/B du 07/10/2026 : photo sans son vs vidéo avec musique).

Buffer ne permet pas d'ajouter un son aux carrousels photo TikTok ; une vidéo, elle, porte sa musique.
media/t/NN/*.png (1080x1920) -> media/v/v3-NN.mp4 : couverture 2 s, slides 3,5 s, dernière 2,5 s,
coupes franches, musique libre de droits (contenu/giletjaune/music, générée par code) en boucle.

Usage :
    python generator/slideshow_v3.py 77 82 81
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MUSIC = ROOT / "contenu" / "giletjaune" / "music"


def durations(n):
    return [2.0] + [3.5] * (n - 2) + [2.5]


def make(cid):
    slides = sorted((ROOT / "media" / "t" / cid).glob("*.png"), key=lambda p: int(p.stem))
    if len(slides) < 2:
        sys.exit(f"media/t/{cid} : slides introuvables (lancer render_v3.py)")
    durs = durations(len(slides))
    total = sum(durs)
    out = ROOT / "media" / "v" / f"v3-{cid}.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for s, d in zip(slides, durs):
        cmd += ["-loop", "1", "-t", str(d), "-framerate", "30", "-i", str(s)]
    cmd += ["-stream_loop", "-1", "-i", str(MUSIC / f"m{int(cid) % 4 + 1}.wav")]
    n = len(slides)
    graph = "".join(f"[{i}]scale=1080:1920,setsar=1,format=yuv420p[s{i}];" for i in range(n))
    graph += "".join(f"[s{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[v];"
    graph += f"[{n}:a]afade=t=in:d=0.3,afade=t=out:st={total - 1:.2f}:d=1,volume=0.8[aud]"
    cmd += ["-filter_complex", graph, "-map", "[v]", "-map", "[aud]", "-t", f"{total:.2f}",
            "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p", "-r", "30",
            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True)
    print(f"  {out.relative_to(ROOT)} ({total:.1f} s, {out.stat().st_size / 1e6:.1f} Mo)")


if __name__ == "__main__":
    for cid in sys.argv[1:]:
        make(cid)
