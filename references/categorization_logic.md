# Logique de catégorisation créative — moteur de référence

Ce fichier porte la logique d'analyse. Le SKILL.md décrit le workflow ; ce document décrit **comment juger une créative**. Les seuils ci-dessous sont des **seuils par défaut** : ils fonctionnent sur la majorité des comptes mais ne remplacent pas une calibration par vertical (e-commerce, SaaS, lead gen), qui n'est pas couverte ici.

## Principe directeur

Une créative ne se juge jamais dans l'absolu. Elle se juge **vis-à-vis de l'objectif de la campagne qui la porte**, parce qu'une campagne de notoriété et une campagne d'acquisition ne cherchent pas la même chose. Juger une créative de notoriété au CAC est une erreur de méthode : elle n'a pas vocation à convertir. Le routage par objectif se fait donc **avant** tout calcul de catégorie.

Deuxième principe, transversal : **une bonne créative est celle que l'algorithme choisit de diffuser.** Quand Meta pousse du budget sur une créative, c'est un vote de confiance de l'algo. La part de budget (dépense créative / dépense campagne) est donc le signal commun aux trois branches, combiné au signal de coût propre à chaque objectif.

Troisième principe : **tous les ratios se recalculent sur les totaux agrégés, jamais en moyennant des ratios.** Un CAC de périmètre = Σ dépense / Σ conversions, pas la moyenne des CAC par créative. Idem CPM, ROAS, CVR, CTR. C'est vrai pour l'agrégation entre créatives comme pour l'agrégation dans le temps (une semaine = somme des dépenses et des conversions de la semaine, puis ratio).

## Étape 0 — Routage par objectif

L'objectif est lu nativement sur la campagne (`objective` de l'API Meta), pas déduit de la nomenclature. On regroupe les objectifs Meta en trois familles :

- **Acquisition** : objectifs orientés vente/conversion à froid (OUTCOME_SALES, OUTCOME_LEADS sur audience froide, conversions).
- **Notoriété** : OUTCOME_AWARENESS, reach, brand awareness, video views.
- **Retargeting** : techniquement souvent OUTCOME_SALES, mais sur audience chaude. La distinction acquisition/retargeting ne se lit pas dans l'objectif natif : elle se lit dans l'audience (audience personnalisée basée sur trafic/panier/engagement) ou, à défaut, dans la nomenclature de campagne/adset. Si ni l'audience ni la nomenclature ne permettent de trancher, classer en acquisition par défaut et le signaler.

## Étape 1 — Garde-fou de maturité (toutes branches)

Avant de catégoriser, vérifier l'âge de la créative. **Sous 96 heures d'activité, une créative n'est pas catégorisée** : elle est marquée `learn` (apprentissage). Raison : Meta laisse l'algorithme optimiser la diffusion pendant les 2 à 4 premiers jours ; les coûts d'une créative fraîche s'améliorent souvent pendant 48 à 96h avant de se stabiliser. Juger Flop une créative de 2 jours produit un faux négatif qui décrédibilise tout le rapport.

La **date de lancement est un KPI en soi**, pas une métadonnée : elle s'affiche dans le rapport, et elle explique pourquoi une créative n'est pas encore jugée.

Seuil par défaut : `days_active >= 4` (96h). Alternative si la donnée de date est absente : plancher d'impressions, `impressions >= 1000`, en dessous duquel le signal est insuffisant.

## Étape 2 — Catégorisation par branche

Quatre catégories : **Winner**, **Improve**, **Neutral**, **Flop**. (Vocabulaire : "Winner" et non "Top".)

Deux variables communes à calculer d'abord :
- `pctSpendCampaign = dépense_créative / dépense_campagne`
- le KPI de coût de référence de la branche (voir ci-dessous)

### Branche ACQUISITION

KPI pilote : **CAC vs CAC moyen de la campagne** (`campAvgCac = dépense_campagne / conversions_campagne`). Le ROAS est affiché en secondaire mais ne pilote pas le classement — il est biaisé par l'attribution de la régie.

```
si conversions == 0 ou null :
    si campAvgCac null/0            -> Neutral
    sinon si dépense >= 5 x campAvgCac -> Flop      (dépense significative, zéro résultat)
    sinon                          -> Neutral
sinon si campAvgCac == null        -> Neutral
sinon si CAC <= campAvgCac x 1.2 :
    si pctSpendCampaign >= 20%     -> Winner
    sinon si pctSpendCampaign >= 5% -> Improve
    sinon                          -> Neutral
sinon                              -> Flop
```

Logique : une créative qui performe est une créative qui dépense beaucoup (l'algo la pousse, donc plus d'impressions) avec un CAC qui reste sous le seuil de référence de la campagne. Le seuil de tolérance de 1,2× absorbe la variance normale. Ces seuils (1.2, 5×, 20%, 5%) sont les seuils par défaut ; ils valent pour une campagne à objectif d'acquisition pure. Ne pas les appliquer aux autres branches.

#### Garde-fou rentabilité — comptes à AOV élevé uniquement

Sur les comptes **high-ticket** (panier moyen élevé : voyage, mobilier, formations…), le CAC seul induit en erreur : une créative au CAC au-dessus de la moyenne peut rester très rentable, et la marquer « Flop » (à couper) serait un faux négatif. Dans ce cas seulement, on ajoute un garde-fou : une créative dont le CAC dépasse le seuil **mais dont le ROAS reste solide (≥ `ROAS_FLOOR`, défaut 6)** est requalifiée en **Improve** (à optimiser) plutôt que Flop.

Ce garde-fou **ne s'active que si l'AOV de périmètre du compte dépasse `AOV_HIGH`** (défaut 200 €). Raison : le ROAS n'est **pas** un bon juge de la performance créative en général (biais d'attribution de la régie) ; on ne lui donne du poids que là où le CAC seul est trompeur, c'est-à-dire sur les gros paniers. Sur un compte à petit panier, le CAC pilote seul et la règle stricte ci-dessus s'applique. Le garde-fou s'auto-active selon l'AOV mesuré (Σ valeur de conversion / Σ conversions du périmètre). Mettre `ROAS_FLOOR = None` dans `scripts/analyze.py` pour le désactiver partout. Même garde-fou, mêmes conditions, appliqué à la branche retargeting.

### Branche NOTORIÉTÉ

KPI pilote : **CPM vs CPM moyen de la campagne/compte**. On ne part jamais d'un standard de marché : on part de l'historique du compte comme point d'ancrage, parce que le CPM acceptable dépend du marché et des objectifs de l'entreprise, rarement maîtrisés. Ordre de lecture : CPM d'abord, puis hook rate (vidéo uniquement), puis CPC/CTR, puis fréquence comme signal de saturation.

```
soit campAvgCpm = dépense_campagne / impressions_campagne x 1000
si campAvgCpm null/0               -> Neutral
sinon si CPM <= campAvgCpm x 1.1 :
    si pctSpendCampaign >= 20%     -> Winner
    sinon si pctSpendCampaign >= 5% -> Improve
    sinon                          -> Neutral
sinon si CPM > campAvgCpm x 1.1 ET fréquence élevée (>= 3.0) ET reach stagnant -> Flop
sinon                              -> Neutral
```

Note fatigue noto : en notoriété, une fréquence qui grimpe pendant que le reach stagne est le signal de saturation le plus fiable. Le CPM qui dérive au-dessus de la moyenne le confirme.

### Branche RETARGETING

KPIs pilotes dans l'ordre : **CAC, taux de conversion, AOV** en primaires ; CTR et CPC en secondaires. **Pas de ROAS** en retargeting (mécaniquement gonflé par l'attribution sur audience chaude, sans valeur de pilotage). Le seuil de part de budget **saute** comme critère de Winner : les audiences de retargeting sont petites par construction, une créative peut être excellente en dépensant peu. Le classement se fait sur le CAC vs la moyenne de la **campagne de retargeting elle-même**, pas du compte.

```
soit rtgAvgCac = dépense_campagne_rtg / conversions_campagne_rtg
si conversions == 0 ou null        -> Neutral
sinon si rtgAvgCac == null         -> Neutral
sinon si CAC <= rtgAvgCac x 1.2    -> Winner
sinon si CAC <= rtgAvgCac x 1.5    -> Improve
sinon                              -> Flop
```

## Étape 3 — Signal de fatigue (axe séparé, toutes branches)

La fatigue n'est **pas une cinquième catégorie**. C'est un axe distinct qui se superpose à la catégorie. Une créative porte les deux : son **état** (Winner/Improve/Neutral/Flop sur la période) et sa **tendance** (en fatigue ou saine). Raison : l'information la plus actionnable d'un rapport, c'est "cette créative est encore Winner mais elle fatigue, prépare le remplacement". Fondre la fatigue dans une catégorie effacerait cette alerte, qui est la plus rentable.

Définition de la fatigue, sur série glissante jour ou semaine (jamais mensuelle — une créative se lit day-to-day ou week-to-week, sinon on rate le phénomène) :

Une créative est **en fatigue** quand, sur la fenêtre récente, on observe **simultanément** :
- la dépense quotidienne sur la créative **reflue** (l'algo la pousse moins),
- la **fréquence augmente** (répétition sur la même audience),
- le **CAC augmente** (le coût de conversion se dégrade).

Repère chiffré de départ : un CAC 7 jours qui dépasse son propre baseline de 25% et plus est un signal de remplacement. À caler par compte.

**Méthode opérationnelle (défaut, implémentée dans `scripts/analyze.py`) : comparaison de deux fenêtres 7 j** — les 7 derniers jours (récente) vs les 7 précédents (prior). Le **flag de fatigue** = les trois signaux *directionnels* réunis : dépense récente < dépense prior (reflux net, ≥ 10 %), fréquence récente > prior, et CAC récent > CAC prior. Le « +25 % » n'est **pas** le seuil du flag : c'est le palier d'escalade « remplacer maintenant ».

Pourquoi 2 fenêtres et pas la fréquence sur 30 j : une créative dont l'algo a **déjà** coupé le budget affiche une fréquence 30 j élevée (héritée) alors qu'elle est en réalité en voie d'extinction, pas en fatigue active. La comparaison récente/prior distingue « fatigue en cours » (à surveiller, préparer le remplacement) de « déjà éteinte » (rien à faire) — et évite les fausses alertes. Quand les conversions manquent sur les deux fenêtres, on retombe sur le signal de saturation seul : fréquence élevée (≥ `FREQ_SAT`) **et** en hausse **et** dépense qui reflue.

## Étape 4 — KPIs conditionnels au format

Le format se déduit de la structure du creative Meta, pas d'un champ dédié : présence de `video_id` → vidéo, `image_hash` → image, `child_attachments` / `object_story_spec` multi-cartes → carrousel.

Certains KPIs n'ont de sens que pour certains formats :
- **Hook rate** (lectures 3s / impressions) et **taux de complétion vidéo** : vidéo uniquement. Ne jamais afficher pour une image ou un carrousel.
  - **Le hook rate est affiché sur CHAQUE créative vidéo, quel que soit l'objectif de campagne** (acquisition, retargeting, notoriété) — pas seulement en notoriété. Il apparaît directement sur la ligne de la créative dans le tableau (« Hook X % ») et dans le détail. `analyze.py` le calcule dès que la donnée 3 s est présente sur l'ad (`hook3s` / `3_second_video_plays` / `video_3_sec_watched_actions`), sinon la clé `hook` est absente et le template affiche « n/a ».
  - **Piège d'accès (MCP Meta officiel)** : au niveau `ad`, le champ 3 s officiel (`3_second_video_plays`) est **adset-level** et rejeté si demandé explicitement ; `video_continuous_2_sec_watched_actions` remonte souvent « Not available ». Les 3 s peuvent apparaître en « bonus » au niveau ad quand on demande `video_p100_watched_actions` dans un jeu de champs large, mais **de façon non fiable**. Pour un hook garanti sur toutes les périodes, pull les 3 s au **niveau adset** (où c'est supporté) et mappe adset→ad, ou accepte « n/a » sur les fenêtres où Meta ne les fournit pas.
- **Swipe rate** carrousel : non exposé nativement par l'API (calcul dérivé des vues de cartes). **Écarté du rapport par défaut** — dépend de breakdowns pas toujours disponibles, alourdit la lecture, et relève de l'analyse fine à plus forte valeur. À réserver à une version calibrée.

## Étape 5 — Garde-fou tracking et mode dégradé

Les recommandations ne sont possibles que si la donnée est compréhensible. Le skill bascule en **mode dégradé** si l'un de ces signaux apparaît :
- absence totale de conversions sur le périmètre tracké,
- granularité de conversion manquante (fréquent en e-commerce mal taggé),
- montants aberrants (valeurs de conversion délirantes, CAC absurdes).

En mode dégradé, le skill **ne refuse pas d'exécuter**. Il produit le verdict sur ce qui est fiable (diffusion, CPM, CTR, fréquence, fatigue) et **pousse une recommandation méthodologique** de correction du tracking/nomenclature, au lieu de recommander des arbitrages sur une donnée fausse. Le manque de nomenclature ne bloque que l'analyse funnel (TOF/MOF/BOF) et la distinction acquisition/retargeting, pas le reste.

**Une nomenclature illisible n'est pas un échec technique : c'est une recommandation à formuler**, et un point d'entrée commercial (audit). Le skill signale l'écart entre la convention attendue et la réalité du compte, et pousse une méthode de nomenclature propre.

## Récapitulatif des seuils par défaut

| Paramètre | Valeur par défaut | Branche |
|---|---|---|
| Maturité minimale | 96h (ou 1000 impressions) | Toutes |
| Tolérance CAC (Winner/Improve) | CAC ≤ campAvgCac × 1,2 | Acquisition, RTG |
| Seuil Flop sans conversion | dépense ≥ 5 × campAvgCac | Acquisition |
| Part budget Winner | ≥ 20% | Acquisition, Notoriété |
| Part budget Improve | ≥ 5% | Acquisition, Notoriété |
| Tolérance CPM | CPM ≤ campAvgCpm × 1,1 | Notoriété |
| Fréquence saturation | ≥ 3,0 | Notoriété (fatigue) |
| Tolérance Improve RTG | CAC ≤ rtgAvgCac × 1,5 | Retargeting |
| Garde-fou ROAS (Flop→Improve) | ROAS ≥ 6 (`ROAS_FLOOR`) | Acquisition, RTG — **si AOV élevé** |
| Seuil AOV du garde-fou | AOV périmètre ≥ 200 € (`AOV_HIGH`) | Active/désactive le garde-fou |
| Fatigue — flag | reflux ≥ 10% + fréquence ↑ + CAC ↑, sur 2 fenêtres 7j | Toutes |
| Fatigue — escalade « remplacer » | CAC 7j ≥ +25% vs baseline | Toutes |

Ces valeurs sont le point de départ. La calibration par vertical et par compte se fait côté Data Détective — elle ne figure pas dans ce fichier.
