#!/usr/bin/env python3
"""
Injecte les données d'analyse dans le template HTML de rapport Data Détective.

Usage :
    python build_report.py <creas.json> <meta.json> <output.html>

- creas.json : les créatives à afficher. Deux formes acceptées :
  * mono-période : une **liste** d'objets créative (l'ancien format). Elle est
    injectée comme la période 30 j par défaut (`{"30": [...]}`).
  * multi-période : un **dict** {"7":[...], "14":[...], "30":[...]} (une ou
    plusieurs périodes). Le sélecteur 7/14/30 j du rapport bascule alors
    réellement de dataset. Les périodes absentes voient leur bouton désactivé.
  Chaque objet créative doit contenir : name, camp, obj (acq|noto|rtg),
  fmt (video|image|carousel), days, cat (winner|improve|neutral|flop|learn),
  fatigue (true|false|null), spend, conv, cac, roas, ctr, cpm, cpc, freq, pct,
  et selon dispo cvr, aov, hook, reach. Voir references/data_access.md.
- meta.json : métadonnées du rapport (facultatif). Clés reconnues :
  * "subhead" : sous-titre compte/période.
  * "recos"   : recommandations injectées, structure
      {"overview":[...], "acq":[...], "noto":[...], "rtg":[...]}.
      Chaque reco = {"p": <priorité int>, "c": "var(--orange)"|"var(--blue)",
      "t": "<texte HTML>"}. Clés absentes -> section vide (rien ne s'affiche).
  * "deltas"  : variations "vs préc." des KPI cards, par bloc, ex.
      {"overview": {"spend": 8.4, "cac": -4.8, "count": 20, "winners": 50},
       "acq": {"spend": ..., "cac": ..., "count": ..., "roas": ...},
       "noto": {"spend": ..., "cpm": ..., "count": ..., "hook": ...},
       "rtg": {"spend": ..., "cac": ..., "cvr": ..., "aov": ...}}.
      Toute valeur/bloc absent -> chip masquée (jamais de valeur inventée).
      Fournir `null` (ou omettre `deltas`) masque tous les deltas.
- output.html : chemin du rapport généré.

Le template contient les marqueurs `/*__CREAS_DATA__*/`, `/*__RECOS_DATA__*/`,
`/*__DELTAS_DATA__*/` et `/*__SUBHEAD__*/`. Ce script les remplace. Il ne
recalcule pas les catégories : la catégorisation est faite en amont par
analyze.py selon references/categorization_logic.md.
"""
import json
import sys
import os

TEMPLATE = os.path.join(os.path.dirname(__file__), "..", "assets", "report_template.html")

EMPTY_RECOS = {"overview": [], "acq": [], "noto": [], "rtg": []}
EMPTY_DELTAS = {"overview": None, "acq": None, "noto": None, "rtg": None}


def normalize_creas(creas):
    """Retourne un dict {période(str): [créas]} quel que soit le format d'entrée."""
    if isinstance(creas, dict):
        # multi-période : on garde les clés telles quelles (str)
        return {str(k): v for k, v in creas.items()}
    # mono-période : liste -> période 30 j par défaut
    return {"30": creas}


def count_creas(by_period):
    """Nombre de créas de la période la plus longue (pour le message final)."""
    if not by_period:
        return 0
    longest = max(by_period, key=lambda k: int(k))
    return len(by_period[longest])


def build(creas_path, meta_path, out_path):
    with open(TEMPLATE, encoding="utf-8") as f:
        html = f.read()

    with open(creas_path, encoding="utf-8") as f:
        creas = json.load(f)
    by_period = normalize_creas(creas)

    # Injection des datasets (JSON valide = littéral JS valide)
    creas_js = json.dumps(by_period, ensure_ascii=False)
    html = html.replace("/*__CREAS_DATA__*/{\"30\":[]}", creas_js)

    # meta : subhead + recos + deltas
    subhead = ""
    recos = dict(EMPTY_RECOS)
    deltas = dict(EMPTY_DELTAS)
    if meta_path and os.path.exists(meta_path):
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
        subhead = meta.get("subhead", "")
        if isinstance(meta.get("recos"), dict):
            recos = {**EMPTY_RECOS, **meta["recos"]}
        d = meta.get("deltas")
        if isinstance(d, dict):
            deltas = {**EMPTY_DELTAS, **d}

    html = html.replace("/*__RECOS_DATA__*/{overview:[],acq:[],noto:[],rtg:[]}",
                        json.dumps(recos, ensure_ascii=False))
    html = html.replace("/*__DELTAS_DATA__*/{overview:null,acq:null,noto:null,rtg:null}",
                        json.dumps(deltas, ensure_ascii=False))
    html = html.replace("/*__SUBHEAD__*/", subhead)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    n = count_creas(by_period)
    periods = ", ".join(sorted(by_period, key=lambda k: int(k)))
    print(f"Rapport généré : {out_path} ({n} créatives, périodes : {periods} j)")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    creas = sys.argv[1]
    meta = sys.argv[2] if len(sys.argv) > 3 else None
    out = sys.argv[-1]
    build(creas, meta, out)
