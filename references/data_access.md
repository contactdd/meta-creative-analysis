# Accès aux données et champs requis

Trois chemins d'accès à la donnée Meta. **Le consultant choisit explicitement au lancement (Phase 1)** — c'est une question à poser *avant* tout pull, pas une détection automatique. Ne jamais basculer silencieusement d'un canal à l'autre : si le canal annoncé échoue, le signaler et re-demander.

Quel que soit le canal, on récupère la même chose : au **niveau ad (créative)**, sur la période analysée, plus **deux fenêtres 7 j** (récente + précédente) pour la fatigue. Objectif et structure se lisent au niveau campagne/ad.

---

## Chemin 1 — MCP Meta Ads (natif)

Connexion API directe. Deux familles de MCP existent selon ce qui est branché ; **demander/vérifier laquelle** avant de pull.

### 1a. MCP « insights » (Pipeboard, Windsor-natif, ou équivalent avec `get_insights`)
API proche de l'API Marketing. Champs typiques :
- Campagne : `id`, `name`, `objective`, `status`.
- Adset : `id`, `name`, `targeting` (froid vs custom audience).
- Ad + creative : `id`, `name`, `creative{id, object_story_spec, image_hash, video_id, child_attachments, thumbnail_url, instagram_permalink_url, effective_object_story_id}`.
- Insights (niveau ad, `time_increment=1` si série souhaitée, sinon agrégé) : `spend`, `impressions`, `reach`, `frequency`, `clicks`, `inline_link_clicks`, `ctr`, `cpm`, `cpc`, `actions` (dont `purchase` / `omni_purchase`), `action_values`, `purchase_roas`, `video_3_sec_watched_actions` / `video_p100_watched_actions` (hook rate / complétion).

### 1b. MCP Meta officiel (outils `ads_get_ad_entities` + `ads_get_field_context`)
C'est le MCP le plus courant. Il ne se pilote **pas** comme l'API brute — mapping concret, testé :

- **Toujours vérifier les champs avant** avec `ads_get_field_context(field_names=[...])`. Il résout les alias et dit quels champs existent à quel niveau (campaign / adset / ad).
- **Découvrir les comptes** : `ads_get_ad_accounts` (regarder `is_queryable` ; sinon remonter `not_queryable_reason`).
- **Pull entités + métriques** : `ads_get_ad_entities(ad_account_id, level, fields, date_preset|time_range, sort, limit)`.
  - `level` : `campaign` puis `ad`.
  - `date_preset` : `last_7d`, `last_14d`, `last_30d`… ou `time_range={"since":"YYYY-MM-DD","until":"YYYY-MM-DD"}`.
- **Mapping des champs** (noms exacts à passer dans `fields`) :

| Besoin | Champ natif |
|---|---|
| Dépense | `amount_spent` (alias `spend`) |
| Impressions / reach / fréquence | `impressions`, `reach`, `frequency` |
| Clics / clics lien | `clicks`, `actions:link_click` |
| CTR / CPM / CPC | `ctr`, `cpm`, `cpc` |
| **Achats** | `actions:omni_purchase` (int) — **PAS** `purchase` ni `actions` seul |
| **ROAS** | `purchase_roas` |
| Objectif / statut | `objective`, `effective_status` |
| Date de lancement | `created_time` (niveau ad) |
| Complétion vidéo | `video_p100_watched_actions` (le 3 s n'existe qu'aux niveaux account/campaign/adset — hook rate au niveau ad souvent indisponible) |
| Lien créative / campagne | `campaign_id` (sur l'ad) |

- **Pièges à connaître** :
  - Les nombres reviennent **formatés FR** : `"2 141,63 € (EUR)"`, `"242 661"` (espaces insécables ` ` / ` `), `"3,77 %"`. Normaliser avant tout calcul (voir helper `frnum` dans `scripts/analyze.py`).
  - Une métrique absente vaut la chaîne `"Not available"` — **jamais 0** (cf. règle plus bas).
  - `actions`/`action_values` ne se demandent pas en bloc : passer les sous-champs préfixés (`actions:omni_purchase`, `actions:link_click`).
  - `objective` est souvent `OUTCOME_SALES` pour acquisition *et* retargeting → la distinction se fait à la nomenclature (voir `categorization_logic.md` étape 0).

### Fatigue en 2 fenêtres (recommandé, tous MCP)
Plutôt qu'une série quotidienne sur tous les ads, pull **deux agrégés 7 j** au niveau ad : fenêtre récente (`last_7d`) et fenêtre précédente (`time_range` des 7 jours d'avant). Une créative est en fatigue si, entre précédente → récente : **la dépense reflue, la fréquence monte, et le CAC augmente (≥ +25 %)**. Léger, suffisant, fidèle à la méthode.

---

## Chemin 2 — Connecteur Supermetrics (MCP Supermetrics)

Quand le compte est branché à Supermetrics. Workflow du MCP Supermetrics (respecter l'ordre) :

1. `data_source_discovery()` — lister les sources ; repérer **Facebook Ads / Meta Ads** et son `ds_id`, vérifier le statut d'auth. Si non authentifié, partager le lien de login renvoyé par `data_source_discovery(ds_id=X)` et s'arrêter là.
2. `data_source_discovery(ds_id=X)` — lire la config : `has_account_list`, `has_fields`, `report_types`, `is_date_range_required`.
3. `accounts_discovery(ds_id=X)` — récupérer le(s) compte(s) ; si un seul, le sélectionner d'office.
4. `field_discovery(ds_id=X)` — récupérer les **IDs de champs** (jamais les noms d'affichage). Champs à mapper : dépense, impressions, reach, fréquence, clics, clics lien, CTR, CPM, CPC, **achats** (conversions), **valeur de conversion**, ROAS, date de lancement, nom d'ad, nom de campagne, objectif.
5. `data_query(ds_id=X, ds_accounts=..., fields=[...], settings={report_type, date_range, ...})` — au **niveau ad**, avec une dimension **date** si on veut les fenêtres. Puis `get_async_query_results(schedule_id=...)` jusqu'à complétion.

**Limites à vérifier** : selon la config du connecteur, la granularité par jour et les breakdowns créatifs peuvent être bridés. S'assurer que `spend, impressions, conversions, conversion_value, frequency, reach` sont dispos au niveau ad. Le **lien vers la créative / la miniature est souvent absent** → fallback « nom + format sans visuel » (le template génère de toute façon une vignette par format, aucun visuel externe requis).

---

## Chemin 3 — Export manuel guidé (Ads Manager)

Quand ni MCP ni connecteur. Guider l'export depuis Ads Manager :
- **Niveau : Ad** (créative), pas campagne.
- **Ventilation : par jour** si possible (sinon, exporter la période + les 2 fenêtres 7 j séparément pour la fatigue).
- **Colonnes** : Nom de l'ad, Nom de la campagne, Objectif, Dépense, Impressions, Couverture (reach), Fréquence, Clics (tous), Clics sur lien, CTR, CPM, CPC, Achats, Valeur des achats (ROAS), Lectures vidéo 3 s (si vidéo), Date de création/diffusion.

**Limite connue** : l'export **ne contient ni lien ni miniature** de créative → fallback format + nom (le template gère la vignette par format). Signaler que le lien créative cliquable nécessite le chemin MCP ou Supermetrics.

---

## Règle « Non disponible ≠ zéro »

Si une colonne manque (`conversion_value` non tracké, `video_*` sur un compte sans vidéo, `"Not available"` du MCP natif), **ignorer le KPI concerné sans planter et sans le compter comme zéro**. Un ROAS non calculable s'affiche « — », pas « 0 ». Un hook rate sur une image s'affiche « n/a », pas « 0 % ». Confondre absence et zéro fausse les agrégats et la catégorisation.

## Formules d'agrégation (sur totaux — jamais moyenne de ratios)

```
conversionValue = Σ(ROAS_ligne × dépense_ligne)   quand le ROAS est dispo
ROAS   = Σ conversionValue / Σ dépense
CAC    = Σ dépense / Σ conversions
CVR    = Σ conversions / Σ clics_lien
CTR    = Σ clics / Σ impressions
CPM    = (Σ dépense / Σ impressions) × 1000
AOV    = Σ conversionValue / Σ conversions
CPC    = Σ dépense / Σ clics
Hook rate = Σ lectures_3s / Σ impressions   (au niveau où la donnée vidéo existe)
Fréquence = Σ impressions / Σ reach
```

Ces formules s'appliquent identiquement pour l'agrégation entre créatives et pour l'agrégation temporelle (jour → semaine → mois) : on somme les numérateurs et dénominateurs bruts, puis on calcule le ratio. Jamais une moyenne de ratios.
