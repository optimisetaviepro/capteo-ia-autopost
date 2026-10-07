# Stratégie v3 — sortir du plancher des 250 vues (07/10/2026)

## Diagnostic

Sur 50 posts (stats Buffer du 07/10) :

- **TikTok** : en dehors des 2-3 premiers posts du 1er octobre (900 à 1 800 vues, l'effet « nouveau compte »),
  presque tout s'arrête entre 240 et 300 vues. C'est le **lot test** : TikTok montre le post à environ
  250 personnes, puis ne pousse plus faute de signaux forts. Les chiffres : 2 à 6 s de visionnage,
  0 commentaire, presque 0 partage, 0 abonné gagné.
- **Instagram** : 10 à 30 vues par carrousel, 100 à 140 par Reel. Le compte n'est presque pas montré aux non-abonnés.

Causes, de la plus à la moins importante :

1. **Pas de raison de rester ni d'enregistrer.** Une idée par slide, des définitions (« MCP, c'est… »),
   sur un fond sombre identique à chaque post. On lit la couverture, on swipe et on passe : 2 à 6 s.
2. **Format inadapté à TikTok** : du 4:5 dans un écran 9:16 (bandes), du texte sous la légende et les boutons,
   et **aucun son**. Buffer ne permet pas de choisir un son sur un carrousel photo (vérifié dans son API).
3. **Trop de posts moyens** : 5 par jour sur TikTok. Chacun reçoit son lot test et aucun ne se démarque.
4. **Le compte TikTok s'appelle @cindy_mlm** alors que les slides disaient « @Capteo_IA » :
   quelqu'un qui aime le post ne sait pas qui suivre. Ce n'est pas une pénalité de l'algorithme,
   mais ça tue la conversion en abonnés.
5. **Aucune interaction humaine** autour des posts (réponses aux commentaires, activité dans l'appli).

Ce qui marche chez les comptes IA francophones qui percent (veille du 07/10) : @yyov7 (1,1 M), @ninon.ia (276 K),
@unefille.ia (261 K), @lesitedujour (252 K, uniquement « sites cachés »), @outils_ia0 (79 K, **sans visage**,
carrousels). Les formats qui reviennent : le « site secret », « gratuit / arrête de payer », les **prompts à copier**,
le prompt personnel (« colle ça, il va te dire qui tu es » : 224 K likes en carrousel), le contre-pied sur les
« codes secrets », les comparatifs, et les **séries numérotées** (« partie 2 demain »).

## Ce qui a été changé automatiquement

| Avant | Maintenant (à partir du 08/10) |
|---|---|
| Carrousels 4:5 sombres, 1 idée par slide | **31 carrousels v3** : couverture lime à fort contraste, 9:16 plein écran sur TikTok (4:5 sur Instagram) |
| Définitions | Contenu **à enregistrer** : fiches outils (logo + vraie capture du site), prompts à copier, scénarios du quotidien |
| Posts isolés | **Série « IA gratuites » en 6 parties** (18:30, du 8 au 13/10), chaque partie annonce la suivante |
| TikTok : 5 posts/jour | TikTok : **3 posts/jour** (carrousel 12:15, carrousel 18:30, vidéo 20:00) |
| Pas de son | **Test A/B son** : 8 carrousels publiés en diaporama vidéo avec musique (12:15, un jour sur deux) |
| « @Capteo_IA » sur TikTok | Plus de pseudo sur les slides TikTok tant que le compte n'est pas renommé, appel « Abonne-toi pour la suite » |
| Tableau de bord aveugle sur TikTok | Bug corrigé : les posts TikTok sont reliés au planning, les tests A/B TikTok remontent enfin |

Fichiers : `generator/render_v3.py` (rendu), `generator/slideshow_v3.py` (diaporamas), `contenu/v3/*.json` (textes),
`scripts/plan_v3.py` (planning), `media/t/NN` (TikTok) et `media/c/NN` (Instagram).
Les captures de sites ont aussi servi de vérification : NotebookLM s'appelle désormais « Gemini Notebook »,
et remove.bg arrête son site autonome le 01/12/2026 (remplacé par Photoroom).

## 🔴 À faire par Enzo : ce qui ne s'automatise pas (et qui compte le plus)

1. ✅ **TikTok renommé @capteo_ia (07/10)** : pseudo remis sur les slides TikTok et diaporamas re-rendus.
2. **Instagram** : nom affiché `Capteo | IA & astuces gratuites`, même bio. Épingle le carrousel « 6 sites IA gratuits »
   dès qu'il est publié (08/10, 18:30).
3. **L'heure qui suit 18:30, chaque jour (15 min)** : réponds à **chaque** commentaire, avec une question pour relancer.
   C'est le signal qui fait passer le lot test.
4. **Son tendance (test manuel)** : 2 fois cette semaine, publie toi-même dans l'appli TikTok un carrousel de
   `media/t/NN` avec un son de la page « Tendances ». Préviens-moi avant pour que je le retire de l'automatisation.
5. **Face caméra** : les scripts sont prêts (`capteo-ia-reels/scripts`). Une seule vidéo par semaine avec ta voix
   pèse plus que 10 carrousels pour faire s'abonner les gens.

## Ce qui est réaliste

L'objectif de 10 000 abonnés d'ici le 31/10 suppose **au moins un post viral** (100 000 vues et plus).
Le passage en v3 maximise les chances, mais aucun réglage ne le garantit. Les références trouvées :
un compte de niche gagne en général 1 à 5 abonnés par jour sous 1 000 abonnés, et un seul post qui décolle
change complètement la courbe. Objectif intermédiaire concret : **sortir du plancher**, c'est-à-dire
des posts à plus de 1 000 vues, avec des enregistrements et des abonnements, dès la première semaine de v3.

## Points d'étape

- **10/10** : premiers chiffres v3 (posts du 08/10 de plus de 36 h). « Fais le point sur mes stats ».
- **13/10** : fin de la série « IA gratuites ». On compare v3 à v1/v2 et photo à diaporama, puis on double sur le gagnant.
- **Le planning v3 s'arrête le 23/10** (vidéos Claude Reactions : 21/10) : écrire la suite avant le 20/10
  en reprenant les formats gagnants (`contenu/v3/`, `render_v3.py`, `plan_v3.py`).
