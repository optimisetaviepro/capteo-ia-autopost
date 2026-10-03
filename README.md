# capteo-ia-autopost

Publie automatiquement les carrousels sur Instagram (@capteo_ia) **et** TikTok (@cindy_mlm), et la story récap sur Instagram, via Buffer.

## Comment ça marche (et pourquoi rien n'est raté)

- GitHub Actions lance `scripts/schedule.py` **toutes les heures** (à :17).
- Chaque passage programme dans Buffer tout ce qui est dû dans les **24 h** suivantes (reste sous la limite de 10 posts du plan gratuit).
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

## Lancer à la main

```
gh workflow run autopost.yml
gh run watch
```
