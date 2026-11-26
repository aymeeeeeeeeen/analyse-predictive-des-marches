"""Contrat de lecture du dashboard. Les sorties du modèle viennent de la tâche 5."""

import json
import math
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

import pandas as pd

ROOT = Path(__file__).resolve().parent
SCHEMA = json.loads((ROOT / "contracts/schema.json").read_text(encoding="utf-8"))
KEY = ["case_id", "feature_id", "market_id"]
COVERAGE = {"complete", "partial", "failed", "not_collected"}
SENTIMENT = {"positive", "negative", "neutral", "mixed", "unknown", "not_applicable"}


class DataError(ValueError):
    pass


def read_json(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("objet JSON attendu")
        return data
    except (OSError, ValueError) as exc:
        raise DataError(f"{path.name} — {exc}") from exc


def checked(condition, message):
    if not condition:
        raise DataError(message)


def parse_value(value, kind):
    if value is None or pd.isna(value) or (isinstance(value, str) and not value.strip()):
        checked(kind.endswith("?"), "valeur obligatoire")
        return None
    kind = kind.rstrip("?")
    if kind == "text":
        return str(value).strip()
    if kind == "date":
        if isinstance(value, date):
            return date(value.year, value.month, value.day).isoformat()
        checked(bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(value))), "date AAAA-MM-JJ attendue")
        return date.fromisoformat(str(value)).isoformat()
    n = float(value)
    checked(math.isfinite(n), "nombre fini attendu")
    if kind in ("int", "positive_int", "binary"):
        checked(n >= 0 and n.is_integer(), "entier positif ou nul attendu")
        if kind == "positive_int":
            checked(n > 0, "entier strictement positif attendu")
        if kind == "binary":
            checked(n in (0, 1), "0 ou 1 attendu")
        return int(n)
    if kind == "ratio":
        checked(0 <= n <= 1, "valeur entre 0 et 1 attendue")
    return n


def read_table(path, spec):
    try:
        df = (
            pd.read_csv(path, dtype=str, keep_default_na=False)
            if path.suffix == ".csv"
            else pd.read_parquet(path)
        )
        missing = set(spec["columns"]) - set(df)
        checked(not missing, "colonnes absentes " + ", ".join(sorted(missing)))
        rows, keys = [], set()
        for index, row in enumerate(df.to_dict("records"), 2):
            record = {}
            for col, kind in spec["columns"].items():
                try:
                    record[col] = parse_value(row[col], kind)
                except (TypeError, ValueError) as exc:
                    raise DataError(f"ligne {index}, {col} — {exc}") from exc
            key = tuple(record[c] for c in spec["key"])
            checked(key not in keys, f"doublon de clé {key}")
            keys.add(key)
            rows.append(record)
        return rows
    except Exception as exc:
        raise DataError(f"{path.name} — {exc}") from exc


def config_at(path):
    cfg = read_json(path)
    checked(cfg.get("schema_version") == "0.1", "Version de configuration attendue : 0.1")
    checked(cfg.get("mode") in {"demo", "real"}, "mode attendu : demo ou real")
    checked(isinstance(cfg.get("data_dir"), str) and cfg["data_dir"], "data_dir obligatoire")
    scopes = cfg.get("scopes")
    checked(isinstance(scopes, list) and scopes, "scopes doit contenir un périmètre")
    keys = set()
    for s in scopes:
        checked(
            isinstance(s, dict)
            and all(
                isinstance(s.get(k), str) and s[k].strip() for k in KEY + ["case", "feature", "market"]
            ),
            "périmètre incomplet",
        )
        key = tuple(s[k] for k in KEY)
        checked(key not in keys, f"périmètre en double {key}")
        keys.add(key)
        dates = s.get("cutoffs")
        checked(
            isinstance(dates, list) and dates and s.get("default_cutoff") in dates,
            "dates de coupure ou date par défaut manquantes",
        )
        for day in dates:
            parse_value(day, "date")
    return cfg


def load(config_path):
    cfg = config_at(config_path)
    folder = (config_path.parent / cfg["data_dir"]).resolve()
    manifest = read_json(folder / "manifest.json")
    checked(
        manifest.get("is_synthetic") is (cfg["mode"] == "demo"),
        "Le mode choisi ne correspond pas à is_synthetic dans manifest.json.",
    )
    checked(
        manifest.get("schema_version") == cfg["schema_version"] and manifest.get("dataset_id"),
        "Manifeste incompatible ou dataset_id absent.",
    )
    tables, absent = {}, []
    for name, spec in SCHEMA.items():
        paths = [p for ext in (".csv", ".parquet") if (p := folder / (name + ext)).is_file()]
        checked(len(paths) < 2, f"{name} — garder un seul fichier CSV ou Parquet par table")
        tables[name] = read_table(paths[0], spec) if paths else []
        if not paths:
            absent.append(name)
    for name in ("sem_status", "sem_spec"):
        path = folder / (name + ".json")
        tables[name] = read_json(path) if path.exists() else {}
        if not path.exists():
            absent.append(name)
    validate(tables, absent, cfg["mode"])
    thresholds = {tuple(s[k] for k in KEY): s.get("adoption_threshold") for s in cfg["scopes"]}
    for r in tables["labels"]:
        threshold = thresholds.get(tuple(r[k] for k in KEY))
        if threshold is not None and r["label_status"] == "observed":
            checked(
                type(threshold) is int and threshold > 0,
                "adoption_threshold doit être un entier positif",
            )
            checked(
                r["y"] == int(r["new_brands"] >= threshold),
                "labels — résultat incompatible avec le seuil de marques",
            )
    return cfg, manifest, tables, absent


def validate(t, absent, mode):
    for name, field, parent, target in [
        ("document_topics", "aspect_id", "topics", "aspect_id"),
        ("document_topics", "nlp_run_id", "nlp_runs", "nlp_run_id"),
        ("opinions", "passage_id", "passages", "passage_id"),
        ("opinions", "aspect_id", "topics", "aspect_id"),
        ("opinions", "nlp_run_id", "nlp_runs", "nlp_run_id"),
        ("expression_signals", "opinion_id", "opinions", "opinion_id"),
    ]:
        if parent not in absent:
            allowed = {r[target] for r in t[parent]}
            for r in t[name]:
                checked(r[field] in allowed, f"{name}.{field} introuvable : {r[field]}")
    docs = {}
    for name, source in [("company_documents", "company"), ("consumer_documents", "consumer")]:
        for r in t[name]:
            ident = r["document_id"]
            checked(
                ident not in docs and r["source_type"] == source,
                f"{name} — identifiant ou source incohérents : {ident}",
            )
            checked(
                r["date_status"] in {"verified", "estimated", "unknown"},
                f"{ident} — statut de date inconnu",
            )
            version = r["version_available_at"]
            checked(r["date_status"] != "verified" or version, f"{ident} — version vérifiée sans date")
            checked(
                not version or version >= r["published_at"],
                f"{ident} — version antérieure à la publication",
            )
            if mode == "real":
                checked(
                    urlsplit(r["url"] or "").scheme in ("http", "https"),
                    f"{ident} — URL de source obligatoire",
                )
            docs[ident] = r
    if not {"consumer_documents", "company_documents"}.intersection(absent):
        for r in t["passages"] + t["document_scope"] + t["document_topics"]:
            checked(r["document_id"] in docs, f"document_id introuvable : {r['document_id']}")
    for r in t["opinions"]:
        checked(
            r["sentiment"] in SENTIMENT and r["review_status"] in ("accepted", "needs_review"),
            "opinions — valeur inconnue",
        )
    for r in t["expression_signals"]:
        checked(
            r["signal_value"] in ("present", "not_observed", "uncertain", "not_applicable")
            and r["review_status"] in ("accepted", "needs_review"),
            "expression_signals — valeur inconnue",
        )
    for r in t["company_coverage"] + t["consumer_coverage"]:
        checked(r["coverage_status"] in COVERAGE, "statut de couverture inconnu")
    for r in t["features"]:
        for prefix in ("company", "consumer"):
            n, total, share, cov = [r[prefix + "_" + k] for k in ("on", "total", "share", "coverage")]
            checked(cov in COVERAGE, "features — couverture inconnue")
            if cov in ("not_collected", "failed"):
                checked(
                    n is None and total is None and share is None,
                    "features — collecte absente avec valeur fournie",
                )
            checked(
                n is None or total is None or n <= total,
                "features — volume sur le sujet supérieur au total",
            )
            check_ratio(n, total, share, prefix + "_share")
        check_ratio(r["negative"], r["classifiable"], r["negative_share"], "negative_share")
        if all(r[k] is not None for k in ("classifiable", "unknown", "consumer_on")):
            checked(
                r["classifiable"] + r["unknown"] == r["consumer_on"],
                "features — couverture des opinions incohérente",
            )
    for r in t["predictions"]:
        p, d = r["p_event"], r["decision"]
        checked(
            r["status"] in ("ready", "insufficient_data", "unavailable"), "predictions — statut inconnu"
        )
        if r["status"] == "ready":
            checked(
                p is not None and d == int(p >= r["threshold"]),
                "predictions — décision incompatible avec le seuil",
            )
        else:
            checked(p is None and d is None, "predictions — score pour une prévision indisponible")
    events = {r["event_id"]: r for r in t["adoption_events"]}
    for e in events.values():
        checked(
            e["event_type"] in ("sale", "announcement", "deployment"),
            "adoption_events — type non reconnu",
        )
        if mode == "real":
            checked(
                urlsplit(e["evidence_url"] or "").scheme in ("http", "https"),
                "adoption_events — URL de preuve manquante",
            )
        if e["event_type"] == "sale":
            checked(
                e["evidence_available_at"] >= e["event_date"],
                "adoption_events — preuve de vente antérieure à la vente",
            )
    for r in t["labels"]:
        end = (pd.Timestamp(r["cutoff"]) + pd.DateOffset(months=r["horizon_months"])).date().isoformat()
        checked(r["horizon_end"] == end, "labels — fin d’horizon incompatible")
        if r["label_status"] == "observed":
            checked(
                r["label_available_at"] and r["label_available_at"] >= end,
                "labels — preuve avant la fin de l’horizon",
            )
            checked(
                r["y"] is not None and r["new_brands"] is not None, "labels — observation incomplète"
            )
            if "adoption_events" not in absent:
                brands = set()
                for ident in (r["event_ids"] or "").split("|"):
                    if ident:
                        e = events.get(ident)
                        checked(
                            e
                            and all(e[k] == r[k] for k in KEY)
                            and e["event_type"] == "sale"
                            and r["cutoff"] < e["event_date"] <= end
                            and e["evidence_available_at"] <= r["label_available_at"],
                            f"labels — événement inadmissible {ident}",
                        )
                        brands.add(e["brand_id"])
                checked(
                    len(brands) == r["new_brands"], "labels — nombre de marques différent des preuves"
                )
        else:
            checked(
                r["label_status"] == "unknown"
                and all(r[k] is None for k in ("y", "new_brands", "label_available_at", "event_ids")),
                "labels — résultat renseigné avec un statut inconnu",
            )
    sem = t["sem_status"]
    if sem:
        checked(
            all(k in sem for k in ("case_id", "market_id", "status", "reason", "n_units")),
            "sem_status.json incomplet",
        )
        checked(sem["status"] in ("ready", "exploratory", "not_estimable"), "statut SEM inconnu")
        checked(
            sem["n_units"] is None or type(sem["n_units"]) is int and sem["n_units"] >= 0,
            "effectif SEM invalide",
        )
        if sem["status"] == "not_estimable":
            checked(
                not t["sem_paths"] and not t["sem_measurement"],
                "SEM non estimable avec des résultats chiffrés",
            )
    spec = t["sem_spec"]
    if spec:
        checked(
            all(isinstance(spec.get(k), str) for k in ("case_id", "market_id", "unit"))
            and all(
                isinstance(spec.get(k), list) and all(isinstance(v, str) for v in spec[k])
                for k in ("constructs", "hypotheses")
            ),
            "sem_spec.json incomplet",
        )
        if sem:
            checked(
                all(sem[k] == spec[k] for k in ("case_id", "market_id")), "périmètres SEM différents"
            )


def check_ratio(n, total, ratio, name):
    if n is None or not total:
        checked(
            ratio is None and (total != 0 or n in (None, 0)),
            f"{name} — ratio sans dénominateur exploitable",
        )
    else:
        checked(
            n <= total and ratio is not None and abs(ratio - n / total) <= 0.00051,
            f"{name} — taux incohérent",
        )


def scoped(rows, scope):
    return [r for r in rows if all(r[k] == scope[k] for k in KEY)]


def published_opinions(t, scope, cutoff):
    ids = {
        r["document_id"]
        for r in t["document_scope"]
        if all(r[k] == scope[k] for k in ("case_id", "market_id"))
    }
    docs = {
        r["document_id"]: r
        for r in t["consumer_documents"]
        if r["document_id"] in ids
        and r["date_status"] == "verified"
        and r["version_available_at"]
        and r["version_available_at"] <= cutoff
    }
    passages = {r["passage_id"]: r for r in t["passages"] if r["document_id"] in docs}
    aspects = {r["aspect_id"]: r["label"] for r in t["topics"] if r["feature_id"] == scope["feature_id"]}
    runs = {r["nlp_run_id"]: r["model_version"] for r in t["nlp_runs"] if r["training_cutoff"] <= cutoff}
    return [
        (r, p, docs[p["document_id"]], aspects[r["aspect_id"]], runs[r["nlp_run_id"]])
        for r in t["opinions"]
        if (p := passages.get(r["passage_id"])) and r["aspect_id"] in aspects and r["nlp_run_id"] in runs
    ]
