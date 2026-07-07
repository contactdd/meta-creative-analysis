#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
collect.py — assemble les entrées d'analyze.py à partir de dumps MCP BRUTS.

But : supprimer la transcription/reformatage manuel des sorties MCP (le vrai
goulot de production) et ajouter une QA automatique. On colle la sortie du MCP
Meta VERBATIM dans des fichiers ; ce script les normalise et écrit
ads.json / campaigns.json / windows.json prêts pour analyze.py. Aucun nettoyage
FR n'est requis : analyze.frnum() gère « 2 141,63 € (EUR) », « 3,77 % », etc.

Un « dump » accepté sous 3 formes, indifféremment :
  1. la réponse MCP complète  {"ad_entities": "[...]", "summary": {...}}
     (ad_entities est une CHAÎNE JSON — on la json.loads)
  2. un array JSON              [ {...}, {...} ]
  3. déjà une liste de dicts    (fichier .json normal)

Usage :
  python collect.py --out-dir DIR \
      --ads dump_ads_30.json [dump_more.json ...] \
      --campaigns dump_campaigns.json \
      [--window-recent dump_ads_7.json --window-prior dump_ads_prior7.json] \
      [--hook dump_hook.json] \
      [--routes routes.json]

- --ads : un ou plusieurs dumps ad-level de la période analysée. Fusion + dédup
  par id (dernier gagne). Écrit ads.json.
- --campaigns : dump campaign-level. Écrit campaigns.json = {id:{obj,label}} en
  classant acq/rtg/noto à la NOMENCLATURE (cf. categorization_logic.md étape 0).
  Surchargeable via --routes {"<id>":{"obj":"rtg","label":"..."}}.
- --window-recent / --window-prior : 2 dumps ad-level (2 fenêtres 7 j). Écrit
  windows.json = {id:{recent:{spend,freq,purchases}, prior:{...}}} pour la fatigue.
- --hook : dump ad-level {id: 3s} OU ad-level avec un champ 3s ; injecte hook3s
  dans ads.json (le hook au niveau ad est best-effort côté Meta, cf. doc).
- QA : imprime sur stderr le nb de créas, la réconciliation dépense créas vs
  total campagne, les campagnes sans conversion (angles morts tracking) et la
  couverture hook. À lire avant de générer le rapport.
"""
import json, sys, os, argparse, re

# --- classification objectif à la nomenclature (seuils par défaut, surchargables) ---
RTG_KW  = ("rtg", "retarget", "remarket", "tiède", "tiede", "chaud", "warm", "abandon", "panier abandonn")
NOTO_KW = ("notor", "awareness", "reach", "branding", "brand awareness", "video views", "vues vidéo", "tofu")


def _months():
    return None


def load_dump(path):
    """Retourne une liste de dicts d'ads, quelle que soit la forme du dump."""
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    if isinstance(raw, dict) and "ad_entities" in raw:
        ents = raw["ad_entities"]
        return json.loads(ents) if isinstance(ents, str) else ents
    if isinstance(raw, list):
        return raw
    raise ValueError(f"{path}: forme de dump non reconnue (ni réponse MCP, ni array)")


def frnum(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if s == "" or s.lower() in ("not available", "n/a", "na", "—", "-"):
        return None
    for junk in (" ", " ", " ", "€", "(EUR)", "%", "EUR"):
        s = s.replace(junk, "")
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def classify(name):
    n = (name or "").lower()
    if any(k in n for k in RTG_KW):
        return "rtg"
    if any(k in n for k in NOTO_KW):
        return "noto"
    return "acq"


def short_label(name):
    """Label court lisible depuis le nom de campagne (best-effort)."""
    n = re.sub(r"\s*[-|\[].*$", "", (name or "")).strip()
    return (n[:34] or name or "").strip()


def merge_ads(paths):
    by_id = {}
    for p in paths:
        for a in load_dump(p):
            by_id[str(a.get("id"))] = a
    return list(by_id.values())


def build_campaigns(path, routes):
    camps = {}
    for c in load_dump(path):
        cid = str(c.get("id") or c.get("campaign_id"))
        camps[cid] = {"obj": classify(c.get("name")), "label": short_label(c.get("name"))}
    for cid, ov in (routes or {}).items():
        camps.setdefault(cid, {}).update(ov)
    return camps


def build_windows(recent_path, prior_path):
    def keyed(p):
        d = {}
        for a in load_dump(p):
            d[str(a.get("id"))] = {"spend": a.get("amount_spent"),
                                   "freq": a.get("frequency"),
                                   "purchases": a.get("actions:omni_purchase")}
        return d
    rec, pri = keyed(recent_path), keyed(prior_path)
    out = {}
    for aid in set(list(rec) + list(pri)):
        out[aid] = {"recent": rec.get(aid, {}), "prior": pri.get(aid, {})}
    return out


def attach_hook(ads, hook_path):
    hraw = None
    with open(hook_path, encoding="utf-8") as f:
        hraw = json.load(f)
    if isinstance(hraw, dict):
        hmap = {str(k): v for k, v in hraw.items()}
    else:  # liste d'ads avec un champ 3s
        rows = hraw["ad_entities"] if isinstance(hraw, dict) else hraw
        if isinstance(rows, str):
            rows = json.loads(rows)
        hmap = {}
        for a in rows:
            v = a.get("3_second_video_plays") or a.get("hook3s") or a.get("video_3_sec_watched_actions")
            if v not in (None, "Not available"):
                hmap[str(a.get("id"))] = v
    for a in ads:
        if str(a.get("id")) in hmap:
            a["hook3s"] = hmap[str(a.get("id"))]
    return sum(1 for a in ads if "hook3s" in a)


def qa(ads, campaigns, hook_cov):
    """Contrôles automatiques -> stderr. Attrape ce que l'œil rate."""
    p = lambda *a: print(*a, file=sys.stderr)
    p("=== QA collecte ===")
    p(f"Créatives : {len(ads)}")
    # dépense par campagne (créas) vs objectif routé
    spend_c, conv_c = {}, {}
    for a in ads:
        cid = str(a.get("campaign_id") or a.get("camp"))
        spend_c[cid] = spend_c.get(cid, 0) + (frnum(a.get("amount_spent")) or 0)
        conv_c[cid] = conv_c.get(cid, 0) + (frnum(a.get("actions:omni_purchase")) or 0)
    tot = sum(spend_c.values())
    p(f"Dépense créas (somme) : {tot:,.0f} €".replace(",", " "))
    no_conv = [cid for cid, s in spend_c.items() if s > 50 and conv_c.get(cid, 0) == 0]
    if no_conv:
        p(f"⚠ Campagnes avec dépense >50€ et 0 conversion trackée (angle mort tracking) : "
          + ", ".join(campaigns.get(c, {}).get("label", c) for c in no_conv))
    unrouted = {str(a.get("campaign_id")) for a in ads} - set(campaigns)
    if unrouted:
        p(f"⚠ Campagnes sans routage (obj=acq par défaut) : {sorted(unrouted)}")
    nvid = sum(1 for a in ads if "vidéo" in (a.get("name", "").lower()) or "video" in (a.get("name", "").lower()))
    p(f"Couverture hook : {hook_cov}/{nvid} créas vidéo" if nvid else "Aucune créa vidéo détectée")
    by_obj = {}
    for cid, c in campaigns.items():
        by_obj[c["obj"]] = by_obj.get(c["obj"], 0) + 1
    p(f"Routage objectifs : {by_obj}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=".")
    ap.add_argument("--ads", nargs="+", required=True)
    ap.add_argument("--campaigns", required=True)
    ap.add_argument("--window-recent")
    ap.add_argument("--window-prior")
    ap.add_argument("--hook")
    ap.add_argument("--routes")
    a = ap.parse_args()

    routes = None
    if a.routes:
        with open(a.routes, encoding="utf-8") as f:
            routes = json.load(f)

    ads = merge_ads(a.ads)
    campaigns = build_campaigns(a.campaigns, routes)
    hook_cov = attach_hook(ads, a.hook) if a.hook else 0

    os.makedirs(a.out_dir, exist_ok=True)
    def dump(name, obj):
        with open(os.path.join(a.out_dir, name), "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False)
    dump("ads.json", ads)
    dump("campaigns.json", campaigns)
    if a.window_recent and a.window_prior:
        dump("windows.json", build_windows(a.window_recent, a.window_prior))

    qa(ads, campaigns, hook_cov)
    print(f"OK -> {a.out_dir}/ads.json ({len(ads)} créas), campaigns.json ({len(campaigns)} camp.)"
          + (", windows.json" if a.window_recent else ""), file=sys.stderr)


if __name__ == "__main__":
    main()
