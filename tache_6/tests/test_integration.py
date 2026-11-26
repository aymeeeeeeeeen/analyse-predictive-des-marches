import csv
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

from integration import ROOT, DataError, load, published_opinions


class Contrats(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.demo = root / "fixtures/demo"
        shutil.copytree(ROOT / "fixtures/demo", self.demo)
        self.cfg = root / "config.json"
        shutil.copy(ROOT / "config.json", self.cfg)

    def test_cas_invalides(self):
        cases = json.loads((ROOT / "fixtures/invalides/cas.json").read_text())["cas"]
        for c in cases:
            with self.subTest(c=c["attendu"]):
                p = self.demo / (c["table"] + ".csv")
                src = p.read_bytes()
                with p.open() as f:
                    rows = list(csv.DictReader(f))
                rows[c["line"]].update(c["changes"])
                with p.open("w", newline="") as f:
                    w = csv.DictWriter(f, rows[0].keys())
                    w.writeheader()
                    w.writerows(rows)
                with self.assertRaisesRegex(DataError, c["attendu"]):
                    load(self.cfg)
                p.write_bytes(src)

    def test_chronologie(self):
        cfg, _, t, _ = load(self.cfg)
        s = cfg["scopes"][0]
        rows = published_opinions(t, s, "2020-12-31")
        self.assertEqual([r[2]["document_id"] for r in rows], ["U017"])
        self.assertEqual(rows[0][0]["sentiment"], "negative")
        self.assertEqual(published_opinions(t, s, "2020-09-30"), [])
        self.assertEqual(len(published_opinions(t, s, "2024-03-31")), 2)
        self.assertEqual(len(published_opinions(t, {**s, "market_id": "M2"}, "2024-03-31")), 0)

    def test_lot_partiel_et_parquet(self):
        (self.demo / "labels.csv").unlink()
        p = self.demo / "features.csv"
        pd.read_csv(p).to_parquet(p.with_suffix(".parquet"), index=False)
        p.unlink()
        _, _, t, absent = load(self.cfg)
        self.assertIn("labels", absent)
        self.assertIsNone(t["features"][1]["consumer_share"])
        self.assertEqual(t["features"][3]["consumer_share"], 0.3)
        self.assertEqual(t["features"][3]["negative_share"], 0.4)
        self.assertEqual(t["features"][3]["classifiable"], 10)
        self.assertEqual(t["features"][3]["unknown"], 2)

    def test_modes_et_schema(self):
        cfg = json.loads(self.cfg.read_text())
        cfg["mode"] = "real"
        self.cfg.write_text(json.dumps(cfg))
        with self.assertRaisesRegex(DataError, "is_synthetic"):
            load(self.cfg)
        cfg["mode"] = "demo"
        self.cfg.write_text(json.dumps(cfg))
        p = self.demo / "predictions.csv"
        p.write_text(p.read_text().replace("p_event", "score", 1))
        with self.assertRaisesRegex(DataError, "p_event"):
            load(self.cfg)

    def test_fichier_manquant_dans_interface(self):
        from unittest.mock import patch

        (self.demo / "predictions.csv").unlink()
        with patch.dict("os.environ", {"MARCHE_CONFIG": str(self.cfg)}):
            at = AppTest.from_file(str(ROOT / "app.py")).run()
            self.assertFalse(at.exception)
            self.assertTrue(any("Aucune prévision" in i.value for i in at.info))


class Parcours(unittest.TestCase):
    def test_interface(self):
        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=15).run()
        self.assertFalse(at.exception)
        self.assertEqual(at.metric[0].value, "0,68")
        self.assertFalse(any("Alerte confirmée" in e.value for e in at.markdown))
        at.toggle[0].set_value(True).run()
        self.assertTrue(any("Alerte confirmée" in e.value for e in at.markdown))
        sel = next(s for s in at.selectbox if s.label.startswith("Modèle"))
        sel.set_value(1).run()
        self.assertFalse(at.toggle[0].value)
        at.toggle[0].set_value(True).run()
        self.assertTrue(any("Tendance manquée" in e.value for e in at.markdown))
        at.radio[0].set_value("Opinions").run()
        self.assertFalse(at.exception)
        self.assertEqual([m.value for m in at.metric], ["10", "2", "40 %"])
        self.assertTrue(any("trois menus" in e.value for e in at.markdown))
        at.radio[0].set_value("Marché").run()
        self.assertFalse(at.exception)
        self.assertEqual(len(at.get("plotly_chart")), 1)
        at.radio[0].set_value("PLS-SEM").run()
        self.assertFalse(at.exception)
        self.assertEqual(at.subheader[0].value, "Relations non estimables")
        at.radio[0].set_value("Prévisions").run()
        next(s for s in at.selectbox if s.label == "Date de prévision").set_value("2021-03-31").run()
        self.assertTrue(any("insuffisantes" in e.value for e in at.info))
        at.toggle[0].set_value(True).run()
        self.assertTrue(any("Résultat inconnu" in e.value for e in at.info))


if __name__ == "__main__":
    unittest.main()
