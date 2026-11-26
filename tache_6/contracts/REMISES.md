# Premiers échanges entre les six responsables

Ces champs forment une proposition de contrat pour la première intégration. Les colonnes supplémentaires des producteurs sont acceptées. Avant le premier lot, l’équipe pourra confirmer les noms et les unités ou ajouter un adaptateur. Les noms exacts, les types et les clés du lecteur figurent dans `schema.json`.

| Qui | Premier échange demandé | Comment le contrôler dans le dashboard |
| --- | --- | --- |
| 1 · Cadrage | Périmètre, définition de l’adoption, horizon et deux événements prouvés de `adoption_events.csv`. Distinguer annonce et vente. | Marché affiche les événements dont la preuve était disponible à la date choisie. Après révélation, une prévision retrouve les ventes concernées. |
| 2 · Entreprises | Quelques lignes de `company_documents.parquet` et `company_coverage.csv`, avec les dates de version et les sources. | Contrôler les identifiants et afficher la couverture par source. |
| 3 · Consommateurs | Quelques lignes de `consumer_documents.parquet` et `consumer_coverage.csv`. Garder le texte original et le contexte disponible. | L’extrait d’une opinion renvoie au texte complet du document livré, à sa version et à sa source. |
| 4 · NLP | `topics.csv`, `document_topics.parquet`, `passages.parquet`, `opinions.parquet`, `expression_signals.parquet` et `nlp_runs.csv` pour au moins un avis. | Sélectionner une opinion, retrouver son aspect, son passage, sa source et la date limite d’apprentissage de son modèle. |
| 5 · Modèle | `features.parquet`, `predictions.parquet`, `labels.parquet` pour une même coupure, plus une prévision du modèle de référence. Demander le diagnostic SEM et les exports associés s’ils existent. | Reprendre le score et les indicateurs exportés, comparer à la référence, puis vérifier le résultat observé. La responsabilité de l’entraînement et des métriques globales reste en tâche 5. |
| 6 · Intégration | Rassembler un export dans un répertoire avec un manifeste. Construire `document_scope.csv` à partir du périmètre convenu. Référencer les dates de prévision dans la configuration. | Lancer la commande de contrôle, traiter les incompatibilités avec la personne concernée et parcourir les quatre vues. |

## Format du premier lot

- Une table par fichier. Le lecteur accepte les formats CSV UTF-8 et Parquet, avec le même nom de base. La première version utilise des exemples CSV pour qu’on puisse les lire dans un tableur.
- Le manifeste du lot comporte `dataset_id`, `schema_version` (actuellement `0.1`) et un booléen `is_synthetic`. Pour un lot réel, placer uniquement des fichiers réels dans un nouveau répertoire, utiliser le mode `real` et attribuer un nouvel identifiant au lot. Le responsable d’intégration vérifie la provenance des exports avant de les regrouper.
- Une cellule vide signifie inconnu ou non livré. Une valeur 0 est une observation mesurée. Les taux sont des fractions entre 0 et 1. Les dates exportées ici sont des dates civiles ISO `AAAA-MM-JJ` (coupure en fin de journée, calendrier du marché à convenir). Convertir les horodatages en amont dans le calendrier retenu.
- `case_id + feature_id + market_id + cutoff` identifie un jeu d’indicateurs. Ajouter `horizon_months` pour l’observation, puis `model_id + run_id` pour la prévision. Les fenêtres et le rythme des indicateurs de cette version sont trimestriels.
- Dans `features`, `*_on` compte les documents distincts évoquant la fonction et `*_total` tous les documents admissibles du même corpus. `*_share` est le taux livré par la tâche 5. Pour le sentiment, `negative` est le nombre d’avis négatifs, `classifiable` le nombre d’avis classables, `unknown` les autres avis sur le sujet. La tolérance de contrôle des ratios est de 0,00051. La couverture prend les valeurs `complete`, `partial`, `failed` et `not_collected`.
- `document_scope.csv` relie un document à un cas et un marché. Les aspects reliés à une caractéristique proviennent de `topics`. Les passages affichés doivent appartenir à des avis dont la version est vérifiée à la coupure. Le modèle d’annotation doit lui aussi avoir une date limite d’apprentissage compatible. La sélection d’extraits peut être plus petite que le corpus agrégé.
- Le statut dans `predictions` vaut `ready`, `insufficient_data` ou `unavailable`. Le champ numérique `decision` est vide en cas d’indisponibilité. Les résultats observés se trouvent uniquement dans `labels`. `label_status` vaut `observed` ou `unknown`. Les identifiants de preuve sont séparés par `|`. Le contrôle de dates suppose un horizon en mois calendaires.
- Types d’événements du lecteur initial : `announcement` (annonce), `sale` (mise en vente), `deployment` (déploiement). La cible de la démo compte les premières ventes de marques distinctes. La tâche 1 arbitre l’admissibilité des événements et la couverture des preuves, la tâche 5 construit les étiquettes.
- Les deux JSON SEM (`sem_spec.json` et `sem_status.json`) ont un périmètre cas/marché explicite. Pour cette version, un lot porte au plus un dossier SEM. Les indicateurs et résultats SEM du même lot lui sont rattachés. Un dossier absent laisse cette vue en attente. Les statuts admis sont `ready`, `exploratory`, `not_estimable`.
- Les fichiers absents laissent le lot partiel et leurs vues en attente. Un fichier présent avec colonnes incompatibles, doublon de clé, incohérence contrôlée ou référence introuvable lorsque la table parente est livrée provoque une erreur explicite.

## Quand les fichiers réels arrivent

1. Copier `config.json` vers `config.reel.json`, passer à `"mode": "real"`, définir `data_dir` vers un dossier séparé. Adapter les cas, caractéristiques, marchés, dates et le texte de la cible au cadrage validé.
2. Demander le manifeste, le dictionnaire et les consignes de génération aux producteurs. Vérifier l’unité de chaque colonne. Déposer les tables disponibles dans le dossier du lot et compléter le manifeste de ce lot.
3. Lancer `python run_pipeline.py --config config.reel.json --check`. Un lot partiel peut réussir les contrôles applicables. Les éléments en attente sont recensés dans `outputs/release_manifest.json`.
4. Pour brancher un script Python fourni et revu avec son auteur, compléter `stages` dans l’ordre des dépendances. Chaque entrée est une liste, par exemple `["modules/tache5/exporter.py", "--config", "regles.json"]`. Les chemins sont relatifs au fichier de configuration. La commande `python run_pipeline.py --config config.reel.json --run-stages` lance les scripts, vérifie les sorties et ouvre l’application. Sans cette option, les exports existants sont lus directement.

**Message prêt à envoyer au groupe**

> J’ai préparé la tâche 6 avec un exemple fictif. Dès que vous avez un mini-échantillon, même incomplet, envoyez-moi le fichier, la signification des colonnes et un exemple d’identifiants liés. Pour le premier essai, prenons le même cas, le même marché et la même date. Je pourrai brancher chaque partie au fur et à mesure.
