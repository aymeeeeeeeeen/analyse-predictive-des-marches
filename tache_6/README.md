# Tâche 6 · Application et intégration

Ouvre le tableau de bord sur ton ordinateur pour parcourir les quatre vues avec les données fictives du complément aux livrables. Le projet démarre sans les fichiers des collègues.

## Premier lancement

Décompresse entièrement le ZIP, ouvre le dossier `tache_6` (celui qui contient `app.py`), puis ouvre un terminal dans ce dossier. Utilise **Python 3.12**. Le premier téléchargement des dépendances demande une connexion Internet. L’application s’exécute ensuite localement.

**Windows**, dans PowerShell :

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe run_pipeline.py
```

**macOS ou Linux** :

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python run_pipeline.py
```

Ouvre **http://127.0.0.1:8501** dans le navigateur si l’onglet ne s’ouvre pas automatiquement. Pour arrêter l’application, utilise Ctrl+C dans le terminal. Les lancements suivants ne nécessitent que la dernière commande. Si le port est occupé, ajoute `--port 8502` et ouvre le port 8502.

## Démonstration en deux minutes

1. **Prévisions** s’ouvre sur le 31/12/2020. Le modèle de démonstration affiche 0,68 pour un seuil de 0,60. Active « Afficher le résultat observé ». Deux nouvelles marques fictives commercialisent la caractéristique dans les douze mois, et les preuves sont complètes le 10/01/2022. Change de modèle pour voir la tendance manquée par la référence fictive.
2. **Marché** montre l’évolution des discussions avant la coupure, les volumes et la couverture. Dans la série consommateurs, la collecte de juin est absente. Le graphique laisse un trou. Au 31/03/2021, l’annonce de B apparaît avec un symbole distinct des mises en vente.
3. **Opinions**, au 31/12/2020, affiche 4 avis négatifs sur 10 classables et 2 inconnus. Sélectionne l’extrait U017 pour lire le texte en contexte. Le sarcasme et la frustration y restent incertains. Le texte de U018 a été révisé en 2023 et reste exclu à cette coupure.
4. **PLS-SEM** montre les concepts, les indicateurs proposés et le diagnostic « Relations non estimables ». L’effectif exploitable est inconnu. Pour voir un autre cas de donnée manquante, reviens à **Prévisions**, choisis le 31/03/2021 et révèle le résultat.

## Organisation

| Élément | Utilité |
| --- | --- |
| `app.py` | Quatre vues Streamlit, filtres et révélation du résultat. |
| `config.json` | Périmètres, dates, mode et emplacement du lot. Les étapes de calcul externes peuvent être branchées ici lorsqu’elles arrivent. |
| `integration.py`, `run_pipeline.py` | Lecture des fichiers, contrôles, lancement et empreintes de la livraison. |
| `contracts/schema.json`, `contracts/REMISES.md` | Noms, clés, types et exemples d’échanges à confirmer avec les cinq responsables. |
| `fixtures/demo/`, `fixtures/invalides/` | Lot synthétique valide et modifications volontairement invalides pour tester les contrôles. |
| `integration_report.pdf`, `release_manifest.json` | Bilan de cette version de démonstration et empreintes de la livraison testée. |

## Vérifier ou connecter des données

Dans l’environnement Python installé, lance `python run_pipeline.py --check` pour contrôler les fichiers sans ouvrir l’interface. La commande écrit le manifeste de l’exécution dans `outputs/`. Les tests se lancent avec `python -m unittest discover -s tests -v`. Sans activation de l’environnement, remplace `python` par le chemin de son exécutable, comme dans les commandes ci-dessus.

Les étapes de réception du premier lot réel et un message à partager au groupe figurent dans **contracts/REMISES.md**. Le modèle NLP, la prévision et les analyses SEM seront fournis par leurs responsables. Les exemples actuels testent l’intégration et le parcours utilisateur. Le test avec des archives réelles, les résultats de performance et le lancement sur une machine tierce restent à réaliser.
