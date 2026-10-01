# capteo-ia-autopost

Programme automatiquement dans Buffer les carrousels et la story Instagram (@capteo_ia) du lendemain.
Chaque soir à 20h (Paris), GitHub Actions lance `scripts/schedule.py`. Le script programme tous les éléments
de `planning.json` dus dans les 30 h suivantes et ignore ceux qui sont déjà programmés à la même heure.

Le dépôt doit rester **public** : Buffer télécharge les images via `raw.githubusercontent.com`.

## Ajouter des carrousels

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
