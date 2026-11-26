"""Lance les étapes configurées, contrôle le lot et ouvre l’interface."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from integration import ROOT, SCHEMA, config_at, load


def fingerprint(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config.json")
    parser.add_argument(
        "--check", action="store_true", help="Valider les sorties disponibles et quitter"
    )
    parser.add_argument(
        "--run-stages",
        action="store_true",
        help="Exécuter les commandes Python du fichier de configuration local",
    )
    parser.add_argument("--port", type=int, default=8501)
    args = parser.parse_args()
    path = args.config.resolve()
    cfg = config_at(path)
    if args.run_stages:
        for stage in cfg.get("stages", []):
            if (
                not isinstance(stage, list)
                or not stage
                or not all(isinstance(arg, str) for arg in stage)
            ):
                raise ValueError(
                    "Chaque étape doit contenir le chemin du script Python et ses arguments."
                )
            subprocess.run([sys.executable, *stage], cwd=path.parent, check=True)
    cfg, manifest, tables, absent = load(path)
    folder = (path.parent / cfg["data_dir"]).resolve()
    inventory = {
        p.name: fingerprint(p)
        for p in sorted(folder.iterdir())
        if p.is_file() and (p.name == "manifest.json" or p.stem in tables)
    }
    report = {
        "version": "0.1.0",
        "dataset_id": manifest["dataset_id"],
        "schema_version": cfg["schema_version"],
        "is_synthetic": manifest["is_synthetic"],
        "config_sha256": fingerprint(path),
        "inputs_sha256": inventory,
        "code_sha256": {
            n: fingerprint(ROOT / n)
            for n in (
                "app.py",
                "integration.py",
                "run_pipeline.py",
                "contracts/schema.json",
                "requirements.lock",
            )
        },
        "runs": sorted({r["run_id"] for r in tables["predictions"]}),
        "models": sorted({r["model_id"] for r in tables["predictions"]}),
        "nlp_runs": sorted({r["nlp_run_id"] for r in tables["nlp_runs"]}),
        "rows": {k: len(tables[k]) for k in SCHEMA if k not in absent},
        "pending": absent,
    }
    out = path.parent / "outputs"
    out.mkdir(exist_ok=True)
    (out / "release_manifest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"Lot {manifest['dataset_id']} contrôlé. {len(absent)} fichier(s) en attente. Manifeste dans {out}.",
        flush=True,
    )
    if not args.check:
        return subprocess.call(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                str(ROOT / "app.py"),
                "--server.port",
                str(args.port),
                "--server.address",
                "127.0.0.1",
            ],
            cwd=ROOT,
            env={**os.environ, "MARCHE_CONFIG": str(path)},
        )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        sys.exit(f"Contrôle interrompu — {exc}")
