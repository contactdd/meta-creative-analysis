#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analyze.py — moteur de calcul du skill meta-creative-analysis.

Transforme des lignes d'ads (n'importe quel canal : MCP natif, Supermetrics, export)
en `creas.json` prêt pour scripts/build_report.py : catégorie (winner/improve/neutral/
flop/learn), état de fatigue, et KPIs agrégés. Toute la logique de
references/categorization_logic.md est ici — l'agent n'a plus à la réécrire.

Entrées (JSON) :
  ads.json       : liste d'ads pour la période analysée. Champs par ad (valeurs brutes
                   FR "2 141,63 € (EUR)" ou nombres — frnum() gère les deux ;
                   "Not available"/None/"" = absent, jamais 0) :
                     id, name, campaign_id,
                     spend, impressions, reach, frequency, clicks, link_clicks,
                     ctr, cpm, cpc, purchases, roas,
                     created (date "18 juillet 2025") OU days_active (int)
  campaigns.json : routage par campagne — { "<campaign_id>": {"obj":"acq|noto|rtg",
                   "label":"ASC+ Froide"} }. L'objectif natif (souvent OUTCOME_SALES
                   partout) ne distingue pas acq/rtg : c'est ici qu'on trancre, à la
                   nomenclature (cf. categorization_logic.md étape 0).
  windows.json   : (optionnel, fatigue) { "<ad_id>": {"recent":{"spend","freq","purchases"},
                   "prior":{"spend","freq","purchases"}} }. Deux fenêtres 7 j.

Sortie : creas.json (liste d'objets créative au format attendu par build_report.py).

Usage :
  python analyze.py ads.json campaigns.json [windows.json] > creas.json
  python analyze.py ads.json campaigns.json windows.json creas.json
"""
import json, sys, datetime

# ---------- Seuils par défaut (cf. references/categorization_logic.md) ----------
CAC_TOL      = 1.2    # Winner/Improve : CAC <= campAvgCac × 1.2
FLOP_NO_CONV = 5.0    # Flop sans conversion : dépense >= 5 × campAvgCac
WINNER_PCT   = 0.20   # part de budget campagne pour Winner (acq/noto)
IMPROVE_PCT  = 0.05   # part de budget campagne pour Improve (acq/noto)
CPM_TOL      = 1.1    # notoriété
FREQ_SAT     = 3.0    # notoriété : fréquence de saturation
RTG_IMPROVE  = 1.5    # retargeting : CAC <= rtgAvgCac × 1.5 -> Improve
MATURITY_IMP = 1000   # plancher d'impressions si la date manque
MATURITY_DAY = 4      # 96 h
FATIGUE_CAC  = 1.25   # fatigue : CAC récent >= baseline × 1.25

# Garde-fou rentabilité — ACTIF UNIQUEMENT sur comptes à AOV élevé (high-ticket : voyage,
# mobilier, etc.). Là, le CAC seul induit en erreur : une créa au CAC au-dessus de la
# moyenne peut rester très rentable. Dans ce cas, si le ROAS reste >= ROAS_FLOOR, on la
# classe Improve (à optimiser) plutôt que Flop (à couper).
# Sur un compte à petit panier (AOV < AOV_HIGH), le garde-fou ne s'active PAS : le CAC
# pilote seul, car le ROAS n'est pas un bon juge de la performance créative (biais
# d'attribution). Le garde-fou s'auto-active selon l'AOV de périmètre du compte analysé.
# Mettre ROAS_FLOOR à None pour désactiver totalement le garde-fou.
ROAS_FLOOR = 6.0     # ROAS mini pour requalifier un CAC élevé en Improve
AOV_HIGH   = 200.0   # € : seuil d'AOV de périmètre au-dessus duquel le garde-fou s'active

_MONTHS = {"janvier":1,"février":2,"fevrier":2,"mars":3,"avril":4,"mai":5,"juin":6,
           "juillet":7,"août":8,"aout":8,"septembre":9,"octobre":10,"novembre":11,
           "décembre":12,"decembre":12}


def frnum(v):
    """Parse un nombre en format FR/MCP. 'Not available'/None/'' -> None (jamais 0)."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if s == "" or s.lower() in ("not available", "n/a", "na", "—", "-"):
        return None
    for junk in (" ", " ", " ", "€", "(EUR)", "%", "EUR"):
        s = s.replace(junk, "")
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def fmt_from_name(name):
    """Déduit le format depuis le nom d'ad (fallback quand la structure creative manque)."""
    n = (name or "").lower()
    if "carrousel" in n or "carousel" in n:
        return "carousel"
    if "vidéo" in n or "video" in n:
        return "video"
    return "image"  # statique / collection statique / défaut


def days_active(ad, today=None):
    if ad.get("days_active") is not None:
        return int(ad["days_active"])
    created = ad.get("created")
    if not created:
        return None
    p = str(created).split()
    try:
        d, m, y = int(p[0]), _MONTHS[p[1].lower()], int(p[2])
        ref = today or datetime.date.today()
        return (ref - datetime.date(y, m, d)).days
    except (ValueError, KeyError, IndexError):
        return None


def _num(ad, *keys):
    for k in keys:
        if k in ad:
            return frnum(ad[k])
    return None


def normalize(ads):
    """Nettoie les lignes brutes en dicts numériques."""
    out = []
    for a in ads:
        out.append({
            "id": str(a.get("id")),
            "name": a.get("name", ""),
            "camp": str(a.get("campaign_id") or a.get("camp")),
            "spend": _num(a, "spend", "amount_spent") or 0.0,
            "imp": _num(a, "impressions", "imp") or 0.0,
            "reach": _num(a, "reach") or 0.0,
            "freq": _num(a, "frequency", "freq"),
            "clicks": _num(a, "clicks"),
            "lclk": _num(a, "link_clicks", "actions:link_click") or 0.0,
            "ctr": _num(a, "ctr"),
            "cpm": _num(a, "cpm"),
            "cpc": _num(a, "cpc"),
            "conv": int(_num(a, "purchases", "actions:omni_purchase") or 0),
            "roas": _num(a, "roas", "purchase_roas"),
            # lectures 3 s (hook) — dispo au niveau ad de façon best-effort ; le
            # champ officiel est adset-level. Plusieurs alias possibles selon le canal.
            "hook3s": _num(a, "hook3s", "3_second_video_plays",
                           "video_3_sec_watched_actions", "video_3s"),
            "days": days_active(a),
            "raw": a,
        })
    return out


def campaign_refs(rows):
    """CAC/CPM moyens par campagne (sur totaux)."""
    spend, conv, imp = {}, {}, {}
    for r in rows:
        spend[r["camp"]] = spend.get(r["camp"], 0) + r["spend"]
        conv[r["camp"]] = conv.get(r["camp"], 0) + r["conv"]
        imp[r["camp"]] = imp.get(r["camp"], 0) + r["imp"]
    avg_cac = {c: (spend[c] / conv[c] if conv[c] > 0 else None) for c in spend}
    avg_cpm = {c: (spend[c] / imp[c] * 1000 if imp[c] > 0 else None) for c in spend}
    return spend, avg_cac, avg_cpm


def categorize(r, obj, camp_spend, avg_cac, avg_cpm, guard=False):
    """Retourne (cat, pct, cac). Applique la branche de categorization_logic.md.
    `guard` : garde-fou ROAS actif (True seulement si AOV de périmètre >= AOV_HIGH)."""
    pct = r["spend"] / camp_spend if camp_spend else 0.0
    cac = r["spend"] / r["conv"] if r["conv"] > 0 else None
    # Garde-fou maturité / signal insuffisant
    if (r["days"] is not None and r["days"] < MATURITY_DAY):
        return "learn", pct, cac
    if r["imp"] < MATURITY_IMP or r["spend"] < 12:
        return "neutral", pct, cac

    if obj == "noto":
        if not avg_cpm:
            return "neutral", pct, cac
        if r["cpm"] and r["cpm"] <= avg_cpm * CPM_TOL:
            if pct >= WINNER_PCT: return "winner", pct, cac
            if pct >= IMPROVE_PCT: return "improve", pct, cac
            return "neutral", pct, cac
        if r["cpm"] and r["cpm"] > avg_cpm * CPM_TOL and (r["freq"] or 0) >= FREQ_SAT:
            return "flop", pct, cac
        return "neutral", pct, cac

    # acquisition & retargeting : pilotés au CAC
    if r["conv"] == 0:
        if avg_cac and r["spend"] >= FLOP_NO_CONV * avg_cac:
            return "flop", pct, cac
        return "neutral", pct, cac
    if avg_cac is None:
        return "neutral", pct, cac

    if obj == "rtg":
        # audiences petites : la part de budget ne pilote pas ; conv trop mince -> neutral
        if r["conv"] <= 1 and r["spend"] < 30:
            return "neutral", pct, cac
        if cac <= avg_cac * CAC_TOL: return "winner", pct, cac
        if cac <= avg_cac * RTG_IMPROVE: return "improve", pct, cac
        if guard and ROAS_FLOOR and r["roas"] and r["roas"] >= ROAS_FLOOR and cac <= avg_cac * 2:
            return "improve", pct, cac
        return "flop", pct, cac

    # acquisition
    if cac <= avg_cac * CAC_TOL:
        if pct >= WINNER_PCT: return "winner", pct, cac
        if pct >= IMPROVE_PCT: return "improve", pct, cac
        return "neutral", pct, cac
    if guard and ROAS_FLOOR and r["roas"] and r["roas"] >= ROAS_FLOOR:
        return ("improve" if pct >= IMPROVE_PCT else "neutral"), pct, cac
    return "flop", pct, cac


def fatigue(r, windows):
    """True/False/None. Fatigue = dépense reflue + fréquence monte + CAC monte (>=+25%)."""
    if r["imp"] < MATURITY_IMP or r["spend"] < 15:
        return None
    w = windows.get(r["id"]) if windows else None
    if not w:
        return False
    rec, pri = w.get("recent", {}), w.get("prior", {})
    rs, ps = frnum(rec.get("spend")), frnum(pri.get("spend"))
    rf, pf = frnum(rec.get("freq")), frnum(pri.get("freq"))
    rc, pc = frnum(rec.get("purchases")), frnum(pri.get("purchases"))
    if None in (rs, ps, rf, pf) or ps == 0:
        # fréquence seule : saturation nette si fréquence élevée et en hausse
        if rf and pf and rf >= FREQ_SAT and rf > pf and rs and ps and rs < ps:
            return True
        return False
    spend_reflux = rs < ps * 0.9
    freq_up = rf > pf
    # Flag = les 3 signaux DIRECTIONNELS (cf. categorization_logic.md étape 3).
    # Le CAC "augmente" = hausse simple ; le +25% (FATIGUE_CAC) est le palier
    # "remplacer maintenant", exposé à part, pas le seuil du flag.
    cac_up = True
    if rc and pc and rc > 0 and pc > 0:
        cac_up = (rs / rc) > (ps / pc)
    return bool(spend_reflux and freq_up and cac_up)


def build_creas(ads, campaigns, windows=None):
    rows = normalize(ads)
    camp_spend, avg_cac, avg_cpm = campaign_refs(rows)
    # AOV de périmètre : Σ valeur de conversion / Σ conversions (rows au ROAS connu).
    # Détermine si le compte est "high-ticket" -> active le garde-fou ROAS.
    _cval = sum(r["roas"] * r["spend"] for r in rows if r["roas"] and r["conv"] > 0)
    _conv = sum(r["conv"] for r in rows if r["roas"] and r["conv"] > 0)
    perimeter_aov = (_cval / _conv) if _conv else None
    guard = bool(perimeter_aov and perimeter_aov >= AOV_HIGH)
    creas = []
    for r in rows:
        cinfo = campaigns.get(r["camp"], {})
        obj = cinfo.get("obj", "acq")
        cat, pct, cac = categorize(r, obj, camp_spend.get(r["camp"], 0),
                                   avg_cac.get(r["camp"]), avg_cpm.get(r["camp"]), guard)
        fat = fatigue(r, windows) if cat != "learn" else None
        roas, conv, lclk = r["roas"], r["conv"], r["lclk"]
        cval = roas * r["spend"] if roas else None
        d = {
            "name": r["name"], "camp": cinfo.get("label", r["camp"]),
            "obj": obj, "fmt": fmt_from_name(r["name"]),
            "days": r["days"] if r["days"] is not None else 0,
            "cat": cat, "fatigue": fat,
            "spend": round(r["spend"], 2), "conv": conv,
            "cac": round(cac, 1) if cac else None, "roas": roas,
            "ctr": r["ctr"], "cpm": r["cpm"], "cpc": r["cpc"],
            "freq": r["freq"], "reach": r["reach"], "pct": round(pct * 100, 1),
        }
        if conv > 0 and lclk > 0: d["cvr"] = round(conv / lclk * 100, 2)
        if roas and conv > 0: d["aov"] = round(cval / conv, 0)
        # Hook rate = lectures 3 s / impressions, VIDÉO uniquement, quel que soit
        # l'objectif de campagne. Absent (image/carrousel, ou 3 s non fournis) -> pas
        # de clé "hook" -> le template affiche "n/a".
        if d["fmt"] == "video" and r["hook3s"] and r["imp"] > 0:
            d["hook"] = round(r["hook3s"] / r["imp"] * 100, 1)
        creas.append(d)
    creas.sort(key=lambda c: -c["spend"])
    return creas


def _load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    ads = _load(sys.argv[1])
    campaigns = _load(sys.argv[2])
    windows = None
    out = None
    rest = sys.argv[3:]
    for a in rest:
        if a.endswith("windows.json") or "window" in a:
            windows = _load(a)
        else:
            out = a
    if rest and windows is None and not out:
        # 3e arg ambigu : si c'est un fichier lisible en JSON -> windows, sinon sortie
        try:
            windows = _load(rest[0])
        except Exception:
            out = rest[0]
    creas = build_creas(ads, campaigns, windows)
    js = json.dumps(creas, ensure_ascii=False, indent=1)
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write(js)
        from collections import Counter
        print(f"{len(creas)} créatives → {out} | " +
              str(dict(Counter(c['cat'] for c in creas))), file=sys.stderr)
    else:
        print(js)
