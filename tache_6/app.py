"""Tableau de bord local de la tâche 6."""

from datetime import date
import os
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from integration import ROOT, DataError, load, published_opinions, scoped

st.set_page_config(page_title="Observatoire des mutations de marché", page_icon="◉", layout="wide")
VIEWS = ["Marché", "Opinions", "Prévisions", "PLS-SEM"]
COV = {
    "complete": "complète",
    "partial": "partielle",
    "failed": "échec de collecte",
    "not_collected": "non collectée",
}
SENT = {
    "positive": "Positif",
    "negative": "Négatif",
    "mixed": "Mixte",
    "neutral": "Neutre",
    "unknown": "Inconnu",
    "not_applicable": "Sans objet",
}
EVENT = {"sale": "● Mise en vente", "announcement": "◇ Annonce", "deployment": "▣ Déploiement"}


def day(value):
    return date.fromisoformat(value).strftime("%d/%m/%Y")


def value(n):
    return "Indisponible" if n is None else str(n).replace(".", ",")


def pct(n):
    return "Indisponible" if n is None else f"{100 * n:.1f}".removesuffix(".0").replace(".", ",") + " %"


def source(r, col="url"):
    if r.get(col) and r[col].startswith(("https://", "http://")):
        st.link_button("Ouvrir la source", r[col])


def show_market():
    st.title("Évolution du marché")
    st.caption("Part des documents qui évoquent la caractéristique, par trimestre.")
    history = sorted(
        (r for r in scoped(tables["features"], scope) if r["cutoff"] <= cutoff),
        key=lambda r: r["cutoff"],
    )
    if history:
        fig = go.Figure()
        for field, title, color in [
            ("company", "Entreprises", "#116956"),
            ("consumer", "Consommateurs", "#9a5128"),
        ]:
            fig.add_scatter(
                x=[r["cutoff"] for r in history],
                y=[r[field + "_share"] for r in history],
                name=title,
                mode="lines+markers",
                connectgaps=False,
                line={"color": color, "width": 3},
                hovertemplate="%{x|%d/%m/%Y} · %{y:.0%}<extra>%{fullData.name}</extra>",
            )
        fig.update_layout(
            height=285,
            margin=dict(l=10, r=20, t=15, b=5),
            legend={"orientation": "h"},
            xaxis_title=None,
            yaxis={"tickformat": ".0%", "rangemode": "tozero"},
        )
        picked = st.plotly_chart(
            fig,
            use_container_width=True,
            key="market_chart",
            config={"displayModeBar": False},
            on_select="rerun",
            selection_mode="points",
        )
        points = picked.selection.points
        period = history[-1]["cutoff"]
        source_filter = None
        if points:
            point = points[-1]
            x = str(point.get("x", ""))[:10]
            index = point.get("curve_number", point.get("curveNumber"))
            if x in {r["cutoff"] for r in history} and index in (0, 1):
                period = x
                source_filter = ("company", "consumer")[index]
        with st.expander("Lire des textes associés à un point", expanded=bool(points)):
            st.caption(
                "Clique sur un point de la courbe. Par défaut, les extraits correspondent au dernier trimestre affiché."
            )
            aspects = {
                r["aspect_id"] for r in tables["topics"] if r["feature_id"] == scope["feature_id"]
            }
            runs = {r["nlp_run_id"] for r in tables["nlp_runs"] if r["training_cutoff"] <= period}
            ids = {
                r["document_id"]
                for r in tables["document_topics"]
                if r["assigned"] and r["aspect_id"] in aspects and r["nlp_run_id"] in runs
            }
            ids &= {
                r["document_id"]
                for r in tables["document_scope"]
                if all(r[k] == scope[k] for k in ("market_id", "case_id"))
            }
            period_start = (pd.Timestamp(period).to_period("Q").start_time).date().isoformat()
            excerpts = [
                d
                for d in tables["company_documents"] + tables["consumer_documents"]
                if d["document_id"] in ids
                and d["date_status"] == "verified"
                and d["version_available_at"]
                and d["version_available_at"] <= period
                and period_start <= d["published_at"] <= period
                and (not source_filter or d["source_type"] == source_filter)
            ]
            if excerpts:
                ix = st.selectbox(
                    "Document du trimestre",
                    range(len(excerpts)),
                    format_func=lambda i: f"{excerpts[i]['document_id']} · {excerpts[i]['source_id']}",
                )
                doc = excerpts[ix]
                st.write(doc["text"])
                st.caption(
                    f"{doc['source_id']} · Publication le {day(doc['published_at'])} · Version du {day(doc['version_available_at'])}"
                )
                source(doc)
            else:
                st.info("Aucun extrait fourni pour ce point dans le lot.")
        st.subheader("Volumes et couverture")
        st.dataframe(
            [
                {
                    "Fin de période": day(r["cutoff"]),
                    "Source": title,
                    "Sur le sujet": r[k + "_on"],
                    "Documents admissibles": r[k + "_total"],
                    "Couverture": COV[r[k + "_coverage"]],
                }
                for r in reversed(history)
                for k, title in [("company", "Entreprises"), ("consumer", "Consommateurs")]
            ],
            hide_index=True,
            width="stretch",
        )
    else:
        st.info("Aucun indicateur livré pour ce périmètre avant cette date.")
    coverage = [
        r
        for name in ("company_coverage", "consumer_coverage")
        for r in tables[name]
        if r["case_id"] == scope["case_id"]
        and r["market_id"] == scope["market_id"]
        and r["period_end"] <= cutoff
    ]
    with st.expander("Consulter le journal des collectes"):
        if coverage:
            st.dataframe(
                [
                    {
                        "Fin de période": day(r["period_end"]),
                        "Source": r["source_id"],
                        "État": COV[r["coverage_status"]],
                        "Note": r["comment"],
                    }
                    for r in coverage
                ],
                hide_index=True,
                width="stretch",
            )
        else:
            st.info("Aucun bilan de collecte disponible pour ce périmètre.")
    st.subheader("Événements documentés à la coupure")
    events = [
        e
        for e in scoped(tables["adoption_events"], scope)
        if max(e["event_date"], e["evidence_available_at"]) <= cutoff
    ]
    if not events:
        st.info("Aucun événement documenté à cette date dans le lot livré.")
    for e in sorted(events, key=lambda r: r["event_date"]):
        st.write(
            f"{day(e['event_date'])}　{EVENT[e['event_type']]}　·　Marque {e['brand_id']}　·　{e['product_id']}"
        )
        source(e, "evidence_url")


def show_opinions():
    st.title("Opinions sur la caractéristique")
    if feature:
        a, b, c = st.columns(3)
        a.metric("Avis classables", value(feature["classifiable"]))
        b.metric("Avis inconnus", value(feature["unknown"]))
        c.metric("Avis négatifs parmi les classables", pct(feature["negative_share"]))
        if feature["negative"] is not None and feature["classifiable"]:
            st.caption(f"{feature['negative']} avis négatifs sur {feature['classifiable']} classables.")
    else:
        st.info("Comptes par caractéristique indisponibles à cette date.")
    st.subheader("Extraits consultables")
    rows = published_opinions(tables, scope, cutoff)
    if not rows:
        st.info("Aucun extrait relié à une source et une version admissibles à cette date.")
        return
    st.caption(
        "Choisis un extrait pour lire le passage dans son contexte. Le lot peut contenir seulement une sélection des avis comptés."
    )
    op, p, doc, aspect, model = rows[
        st.selectbox(
            "Extrait",
            range(len(rows)),
            format_func=lambda i: f"{rows[i][2]['document_id']} · {rows[i][3]} · {SENT[rows[i][0]['sentiment']]}",
        )
    ]
    with st.container(border=True):
        st.caption(f"{doc['source_id']}　·　{day(doc['published_at'])}　·　{doc['document_id']}")
        st.write(p["text"])
        st.write(f"**Aspect**　{aspect}　　**Sentiment**　{SENT[op['sentiment']]}")
        st.caption("Décision acceptée" if op["review_status"] == "accepted" else "Décision à vérifier")
        st.write("**Texte complet**")
        st.write(doc["text"])
        st.caption(
            f"Version disponible le {day(doc['version_available_at'])} · Modèle {model} · {op['nlp_run_id']}"
        )
        source(doc)
    for s in tables["expression_signals"]:
        if s["opinion_id"] == op["opinion_id"]:
            label = {
                "uncertain": "incertain",
                "present": "repéré",
                "not_observed": "non repéré",
                "not_applicable": "sans objet",
            }[s["signal_value"]]
            status = "à vérifier" if s["review_status"] == "needs_review" else "accepté"
            st.write(f"{s['signal_name'].capitalize()}　·　{label}　·　{status}")


def show_forecast():
    st.title("Prévisions")
    if scope.get("target"):
        st.write(scope["target"])
    available = [r for r in scoped(tables["predictions"], scope) if r["cutoff"] == cutoff]
    if not available:
        st.info("Aucune prévision livrée pour cette date.")
        return
    available.sort(key=lambda r: (r["model_id"], r["run_id"], r["horizon_months"]))
    selected = st.selectbox(
        "Modèle, exécution et horizon",
        range(len(available)),
        format_func=lambda i: f"{available[i]['model_id']} · {available[i]['run_id']} · {available[i]['horizon_months']} mois",
    )
    pred = available[selected]
    left, right = st.columns(2, gap="large")
    with left:
        st.subheader("À la date de prévision")
        st.caption(day(cutoff))
        if pred["status"] == "ready":
            st.metric("Score de prévision", value(pred["p_event"]))
            st.write(
                ("**Alerte émise**" if pred["decision"] else "**Aucune alerte**")
                + f" au seuil de {value(pred['threshold'])}."
            )
        else:
            st.info(
                "Données insuffisantes pour produire ce score."
                if pred["status"] == "insufficient_data"
                else "Prévision indisponible."
            )
        if feature:
            for field, source_name in [("company", "Entreprises"), ("consumer", "Consommateurs")]:
                if feature[field + "_on"] is not None and feature[field + "_total"] is not None:
                    st.write(
                        f"{source_name} · {feature[field + '_on']} documents sur {feature[field + '_total']} évoquent le sujet."
                    )
        st.caption(f"Horizon de {pred['horizon_months']} mois · Indicateurs {pred['input_version']}")
    with right:
        st.subheader("Résultat observé plus tard")
        toggle_key = "reveal/" + json_key(scope, cutoff, pred)
        if not st.toggle("Afficher le résultat observé", key=toggle_key):
            st.caption("Révèle les observations ultérieures pour les comparer à la prévision.")
            return
        label = next(
            (
                r
                for r in scoped(tables["labels"], scope)
                if r["cutoff"] == cutoff and r["horizon_months"] == pred["horizon_months"]
            ),
            None,
        )
        if not label or label["label_status"] != "observed":
            st.info("Résultat inconnu. Les preuves complètes ne sont pas disponibles.")
            return
        st.metric("Nouvelles marques observées", label["new_brands"])
        st.write(
            f"Horizon terminé le {day(label['horizon_end'])}. Preuves disponibles le {day(label['label_available_at'])}."
        )
        if pred["decision"] is not None:
            st.write(
                "**"
                + {
                    (1, 1): "Alerte confirmée",
                    (1, 0): "Fausse alerte",
                    (0, 1): "Tendance manquée",
                    (0, 0): "Absence d’alerte confirmée",
                }[pred["decision"], label["y"]]
                + "**"
            )
        ids = (label["event_ids"] or "").split("|")
        for e in tables["adoption_events"]:
            if e["event_id"] in ids:
                st.write(f"● {day(e['event_date'])} · Mise en vente · Marque {e['brand_id']}")
                source(e, "evidence_url")


def json_key(scope, cutoff, pred):
    return repr(
        tuple(scope[k] for k in ("case_id", "feature_id", "market_id"))
        + (cutoff, pred["model_id"], pred["run_id"], pred["horizon_months"])
    )


def show_sem():
    st.title("Perceptions exprimées · PLS-SEM")
    st.caption("Dossier de mesure du cas et du marché, toutes périodes du dossier confondues.")
    spec, status = tables["sem_spec"], tables["sem_status"]

    def matches(data):
        return all(data.get(k) == scope[k] for k in ("case_id", "market_id"))

    if matches(spec):
        st.write("**Unité étudiée**　" + spec["unit"])
        st.write("**Concepts**　" + " · ".join(spec["constructs"]))
        for hyp in spec["hypotheses"]:
            st.write("Hypothèse · " + hyp)
    if not matches(status):
        st.info("Dossier de faisabilité en attente pour ce cas et ce marché.")
        return
    st.subheader(
        {
            "not_estimable": "Relations non estimables",
            "exploratory": "Estimation exploratoire",
            "ready": "Estimation disponible",
        }[status["status"]]
    )
    st.write(status["reason"])
    st.caption("Effectif exploitable · " + value(status["n_units"]))
    if tables["sem_indicators"]:
        st.dataframe(
            [
                {
                    "Indicateur": r["item_id"],
                    "Concept": r["construct_id"],
                    "Définition": r["definition"],
                    "État": {"proposed": "proposé", "validated": "validé"}.get(
                        r["validation_status"], r["validation_status"]
                    ),
                }
                for r in tables["sem_indicators"]
            ],
            hide_index=True,
            width="stretch",
        )
    if status["status"] != "not_estimable":
        for name, title in [
            ("sem_measurement", "Qualité des mesures"),
            ("sem_paths", "Relations estimées"),
        ]:
            st.subheader(title)
            if tables[name]:
                st.dataframe(tables[name], hide_index=True, width="stretch")
            else:
                st.info("Table de résultats en attente.")


try:
    cfg, manifest, tables, absent = load(
        Path(os.getenv("MARCHE_CONFIG", str(ROOT / "config.json"))).resolve()
    )
except (DataError, ValueError) as exc:
    st.error(f"Impossible d’ouvrir le lot. {exc}")
    st.stop()

with st.sidebar:
    st.title("Mutations de marché")
    view = st.radio("Vue", VIEWS, index=2)
    st.divider()
    choices = cfg["scopes"]
    for k, label in [("case", "Cas"), ("feature", "Caractéristique"), ("market", "Marché")]:
        ident = {"case": "case_id", "feature": "feature_id", "market": "market_id"}[k]
        names = {s[ident]: s[k] for s in choices}
        current = st.selectbox(label, list(names), format_func=names.get)
        choices = [s for s in choices if s[ident] == current]
    scope = choices[0]
    dates = sorted(set(scope["cutoffs"]))
    cutoff = st.selectbox(
        "Date de prévision",
        dates,
        index=dates.index(scope["default_cutoff"]),
        format_func=day,
        disabled=view == "PLS-SEM",
    )
    st.caption("Lot · " + manifest["dataset_id"])
if manifest["is_synthetic"]:
    st.info("Exemple fictif · Les données et les scores servent à la démonstration.")
if absent:
    with st.expander(f"Livraison partielle · {len(absent)} fichier(s) en attente"):
        st.write(", ".join(absent))
feature = next((r for r in scoped(tables["features"], scope) if r["cutoff"] == cutoff), None)
{"Marché": show_market, "Opinions": show_opinions, "Prévisions": show_forecast, "PLS-SEM": show_sem}[
    view
]()
