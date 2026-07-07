# 🎯 Analyse créative Meta — le skill Claude Code de Data Détective

Un skill [Claude Code](https://claude.com/claude-code) qui transforme les données de ton compte **Meta Ads (Facebook / Instagram)** en un **rapport de décision brandé** : quelles créatives couper, lesquelles scaler, lesquelles surveiller — et lesquelles fatiguent avant qu'il ne soit trop tard.

> Offert par **[Data Détective](https://datadetective.fr)**. Tu l'installes, tu le lances sur ton compte, tu obtiens le rapport en quelques minutes.

---

## Ce que ça fait

À partir de ta donnée Meta Ads, le skill produit un **fichier HTML autoportant** (un seul fichier, à ouvrir dans le navigateur) qui contient :

- une **Overview compte** : budget, CAC moyen, distribution des créatives (Winner / Improve / Neutral / Flop), pipeline par objectif ;
- un **onglet par objectif** (acquisition, notoriété, retargeting) avec KPIs adaptés, nuage de points dépense × efficacité, tableau triable, et **2 à 5 recommandations business** ;
- une **détection de fatigue** créative (dépense qui reflue + fréquence qui monte + coût qui grimpe) ;
- un **sélecteur de période** 7 / 14 / 30 jours qui recalcule tout.

La logique n'est pas générique : **chaque créative est jugée par rapport à l'objectif de sa campagne** (une créa de notoriété ne se juge pas au coût par vente), et tous les ratios se recalculent sur les totaux agrégés.

## Ce qu'il te faut

1. **[Claude Code](https://claude.com/claude-code)** installé.
2. **Python 3** (les scripts n'utilisent que la bibliothèque standard, aucune dépendance à installer).
3. **Une source de données Meta Ads** — au choix :
   - un **MCP Meta** branché dans Claude Code (Meta officiel, Pipeboard, ou équivalent), **ou**
   - un connecteur **Supermetrics**, **ou**
   - un **export Ads Manager** (CSV, niveau *ad*).

> **Pas encore de setup data ?** Pas de panique — [réserve un audit accompagné avec Data Détective](https://cal.com/robin-guedoit-xukrdi/quick-call), on branche ta donnée proprement et on fait l'analyse avec toi.

## Installation

Clone le repo directement dans le dossier des skills de Claude Code :

```bash
git clone https://github.com/<ton-compte>/meta-creative-analysis.git \
  ~/.claude/skills/meta-creative-analysis
```

*(ou télécharge le ZIP et dépose le dossier `meta-creative-analysis` dans `~/.claude/skills/`.)*

Relance Claude Code : le skill est détecté automatiquement.

## Utilisation

Dans Claude Code, lance :

```
/meta-creative-analysis
```

…ou demande simplement « *analyse mes créas Meta* ». Le skill va :

1. **Te demander par quel biais te connecter** à ta donnée Meta (MCP / Supermetrics / export).
2. Récupérer les données au niveau créative (+ deux fenêtres 7 jours pour la fatigue).
3. Catégoriser, détecter la fatigue, calculer les KPIs.
4. Générer le rapport HTML brandé, prêt à présenter.

## Comment ça marche (sous le capot)

```
pull data  →  scripts/analyze.py  →  scripts/build_report.py  →  rapport.html
```

- **`scripts/analyze.py`** — le moteur de calcul : normalisation, catégorisation par objectif, détection de fatigue. Les seuils par défaut sont en tête de fichier, modifiables.
- **`scripts/build_report.py`** — injecte les données dans le template brandé.
- **`assets/report_template.html`** — le design system Data Détective (autoportant).
- **`references/`** — la logique de catégorisation et le mapping des 3 canaux de données.

## Structure du repo

```
meta-creative-analysis/
├── SKILL.md                        # point d'entrée du skill (workflow en 7 phases)
├── references/
│   ├── data_access.md              # les 3 canaux de données + mapping des champs
│   └── categorization_logic.md     # le moteur d'analyse (seuils, branches, fatigue)
├── scripts/
│   ├── analyze.py                  # calcul : catégories + fatigue + KPIs
│   └── build_report.py             # rendu HTML
└── assets/
    └── report_template.html        # template brandé Data Détective
```

## Aller plus loin

Ce skill tourne sur **un compte, à un instant T**. Pour un pilotage **continu, multi-comptes et cross-canaux** (Google, Meta, TikTok…), avec calibration par vertical (e-commerce, SaaS, lead gen), c'est l'offre Data Détective.

👉 **[Réserve un call](https://cal.com/robin-guedoit-xukrdi/quick-call)** · **[datadetective.fr](https://datadetective.fr)**

---

<sub>Fait avec ❤️ par Data Détective. Le rapport généré conserve l'attribution Data Détective — c'est ce qui rend ce skill gratuit. Voir [LICENSE](./LICENSE).</sub>
