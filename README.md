# capteo-ia-autopost

Publie automatiquement les carrousels sur Instagram (@capteo_ia) **et** TikTok (@cindy_mlm), et la story récap sur Instagram, via Buffer.

## Comment ça marche (et pourquoi rien n'est raté)

- GitHub Actions lance `scripts/schedule.py` **deux fois par heure** (à :17 et :47), car GitHub saute souvent des passages planifiés.
- Chaque passage programme dans Buffer tout ce qui est dû dans les **6 h** suivantes (`WINDOW_HOURS`, pour rester sous la limite de 10 posts programmés du plan gratuit).
- **Rattrapage** : un élément dont l'heure est passée depuis moins de 6 h et qui n'a pas été publié (ou dont la publication a échoué dans Buffer) est publié immédiatement.
- **Anti-doublon** : un post déjà présent (même texte, même image de story ou même heure) n'est jamais recréé.
- **Tentatives** : chaque appel à Buffer est retenté 4 fois en cas de panne réseau.
- **Alertes** : si un élément ne peut pas être programmé, ou si le planning se termine dans moins de 3 jours, le passage échoue et GitHub envoie un **mail**.
- **Toujours actif** : le workflow se réactive lui-même via l'API GitHub, pour ne pas être coupé après 60 jours sans commit.

Le dépôt doit rester **public** : Buffer télécharge les images via `raw.githubusercontent.com`.

## Ajouter des carrousels (méthode rapide)

1. Écrire le contenu dans un nouveau fichier `contenu/semaine-N.json` (même format que les autres : `id`, `short`, `kicker`, `title`, `subtitle`, 3 `slides`, `cta`, `caption`).
2. Générer les visuels, les stories récap et le planning (3 carrousels par jour à 16:00, 16:45, 17:30 + story à 18:00, heure d'été/hiver gérée) :
   ```
   pip install playwright && playwright install chromium   # une seule fois
   python generator/render.py --start AAAA-MM-JJ           # premier jour libre du planning
   ```
3. Vérifier : `python scripts/schedule.py --dry-run --now 2026-10-23T15:00:00+00:00`
4. `git add . && git commit -m "Planning du …" && git push`

## Ajouter des carrousels à la main


1. Copier les slides dans `media/c/NN/1.png … 5.png` (1080x1350, 2 à 10 images, numérotées à partir de 1).
2. Copier la story éventuelle dans `media/s/story_jourNN.png` (1080x1920).
3. Ajouter les entrées dans `planning.json` :
   ```json
   { "at": "2026-10-09T16:00:00+02:00", "type": "carousel", "media": "c/24", "text": "Description…" },
   { "at": "2026-10-09T18:00:00+02:00", "type": "story", "media": "s/story_jour09.png", "text": "" }
   ```
   ⚠️ À partir du 25 octobre (heure d'hiver), le décalage passe à `+01:00`.
4. Vérifier : `python scripts/schedule.py --dry-run --now 2026-10-08T18:00:00+00:00`
5. `git add . && git commit -m "Planning du 9 octobre" && git push`

## Vidéos (Reels Instagram + TikTok)

Les vidéos de la série « Claude Reactions » sont publiées **2 fois par jour, à 12:30 et 20:00**, sur Instagram (Reel) et TikTok, avec le label « contenu généré par IA ».

- Fichiers : `media/v/NN-slug.mp4` (1080x1920, H.264, ≈ 6 Mo).
- Entrée du planning : `{ "at": "…", "type": "video", "media": "v/06-forma.mp4", "text": "légende", "cover_ms": 3700 }`
  (`cover_ms` = instant de la vidéo utilisé comme couverture ; Buffer n'accepte pas de miniature à part).
- Ajouter de nouvelles vidéos : les réencoder dans `media/v/`, puis `python scripts/add_videos.py --start AAAA-MM-JJ`
  (légendes lues dans `claude-reactions/PUBLICATION.md`, créneaux libres suivants), puis `--dry-run`, commit, push.
- Fenêtre de programmation de **6 h** (variable `WINDOW_HOURS` du workflow) pour rester sous la limite Buffer
  de 10 posts programmés pour toute l'organisation.

## Lancer à la main

```
gh workflow run autopost.yml
gh run watch
```

## Stratégie v2 et tests A/B (depuis le 05/10/2026 après-midi)

- **Instagram : 2 posts par jour** au lieu de 6 : le carrousel de 16:00 et le Reel de 20:00. Plus de story récap.
  **TikTok** garde tout (3 carrousels + 2 vidéos).
  Clé `"networks": ["instagram", "tiktok"]` sur chaque élément du planning (absente = comportement par défaut).
- **Accroches v2** : les couvertures des carrousels 24 à 65 parlent d'un problème du lecteur au lieu de définir un mot
  (ancien titre conservé dans `title_v1` de `contenu/*.json`). Clé `"hook": "v2"` dans le planning.
- **Label IA** : `"ai_label": false` un jour sur deux (jours impairs) sur les vidéos, pour mesurer son effet.
  Les vidéos sont du motion design codé, sans image réaliste générée.
- **Tableau de bord** : `.github/workflows/metrics.yml` lance chaque matin `scripts/metrics.py`, qui écrit
  `stats/posts.csv` et `stats/RAPPORT.md` (top 5 par réseau et verdict de chaque test). À la main :
  `gh workflow run metrics.yml`.
