# 03 — Architecture globale du pipeline

**Projet :** Automatisation de la collecte et de l'historisation des indicateurs économiques
**Étape :** 3 — Conception de l'architecture globale

---

## 1. Objectif de ce document

Définir le plan d'ensemble du système avant tout développement : les grandes couches du pipeline, ce que fait chacune, comment les données circulent entre elles, et où se situe précisément la logique métier de fusion et d'historisation.

---

## 2. Schéma d'architecture en couches

```
┌──────────────────────────────────────────────────────────────────┐
│  COUCHE 1 — SOURCES (externes, hors de notre contrôle)            │
│  Maadialna (Web) │ MHPV (PDF) │ Excel OC │ Base OC │ PortWatch (API)│
└──────────┬───────────┬────────────┬──────────┬──────────┬─────────┘
           │            │            │          │          │
           ▼            ▼            ▼          ▼          ▼
┌──────────────────────────────────────────────────────────────────┐
│  COUCHE 2 — EXTRACTION (un module indépendant par source)         │
│  Chaque module sait UNIQUEMENT parler à SA source.                │
│  Il produit un fichier brut, tel quel, horodaté, non modifié.     │
└──────────────────────────────┬─────────────────────────────────────┘
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│  ZONE DE STOCKAGE BRUT (data/raw/)                                 │
│  Copie exacte de ce qui a été récupéré, jamais écrasée.            │
│  Sert de point de rejeu en cas de bug plus loin dans le pipeline.  │
└──────────────────────────────┬─────────────────────────────────────┘
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│  COUCHE 3 — TRANSFORMATION (un module par source)                  │
│  Chaque source (JSON, HTML, PDF, Excel) est convertie vers UN      │
│  format commun (schéma pivot) : indicateur, période, valeur,       │
│  unité, source, statut.                                            │
└──────────────────────────────┬─────────────────────────────────────┘
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│  COUCHE 4 — NETTOYAGE (générique, s'applique à toutes les sources)│
│  Doublons, valeurs manquantes, types de données, unités.           │
└──────────────────────────────┬─────────────────────────────────────┘
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│  COUCHE 5 — FUSION & HISTORISATION (cœur métier du projet)         │
│  - Commerce extérieur : la donnée Base OC remplace l'Excel         │
│    période par période, dès qu'elle devient disponible.            │
│  - Chaque changement de valeur crée une NOUVELLE ligne historisée, │
│    jamais un écrasement.                                            │
│  - Chaque ligne porte un statut : provisoire / révisé / consolidé. │
└──────────────────────────────┬─────────────────────────────────────┘
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│  COUCHE 6 — STOCKAGE FINAL (PostgreSQL)                            │
│  Base unique, modèle en étoile (détaillé à l'Étape 6).             │
└──────────────────────────────┬─────────────────────────────────────┘
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│  COUCHE 7 — VISUALISATION (Power BI)                                │
│  Connexion directe à PostgreSQL, rafraîchissement planifié.         │
└──────────────────────────────────────────────────────────────────┘
```

---

## 3. Rôle de chaque couche

| Couche | Rôle en une phrase |
|---|---|
| 1. Sources | Les 5 systèmes externes qui publient les données ; on ne les contrôle pas, on s'y adapte. |
| 2. Extraction | Aller chercher la donnée telle qu'elle existe chez la source, sans la modifier. |
| Zone `data/raw/` | Conserver une copie horodatée, intacte, de tout ce qui a été extrait — la preuve de ce qui existait à un instant T. |
| 3. Transformation | Faire passer chaque source, quelle que soit sa forme d'origine, dans un même schéma de colonnes (le format pivot). |
| 4. Nettoyage | Améliorer la qualité des données une fois qu'elles sont toutes dans le même format : doublons, valeurs manquantes, types, unités. |
| 5. Fusion & Historisation | Appliquer la règle métier (Base OC = référence, Excel = complément des mois récents) et garantir qu'aucune valeur n'est perdue lors d'une révision. |
| 6. Stockage final | Centraliser le résultat dans une base unique, structurée pour l'analyse. |
| 7. Visualisation | Donner accès au résultat final via des tableaux de bord Power BI. |

---

## 4. Association source → format brut attendu

| Source | Type de fichier brut conservé dans `data/raw/` |
|---|---|
| Maadialna (Web) | Extrait JSON horodaté (valeurs scrapées à chaque exécution) |
| MHPV — vente de ciment (PDF) | Fichier PDF original conservé tel que téléchargé, + JSON extrait des tableaux |
| Excel OC — Produits remarquables | Fichier `.xlsx` original conservé tel que téléchargé |
| Base statistique OC | Export brut de la requête (CSV ou JSON selon la méthode d'accès retenue) |
| PortWatch (API) | Réponse JSON brute de l'appel API, horodatée |

---

## 5. Les 3 principes d'architecture

1. **Isolation des sources** — chaque extracteur ne connaît que sa propre source. Un changement de structure chez une source ne casse qu'un seul module, jamais l'ensemble du pipeline.
2. **Rien n'est jamais écrasé, à aucune couche** — le brut est conservé indéfiniment ; la couche Fusion & Historisation crée de nouvelles versions plutôt que de modifier une ligne existante.
3. **Un seul format pivot** — toutes les sources convergent vers le même schéma de colonnes en sortie de la Transformation, ce qui permet au Nettoyage et à la Fusion de traiter toutes les sources avec un code commun, sans cas particulier pour chacune.

---

## 6. Points d'attention spécifiques à ce projet

- La couche **Fusion & Historisation** ne concerne pleinement que 2 des 5 sources (Excel OC et Base OC), puisque ce sont les deux seules à mesurer la même réalité (le commerce extérieur) à deux vitesses différentes. Maadialna, le PDF ciment et PortWatch sont des indicateurs indépendants qui s'ajoutent au système sans suivre cette logique de remplacement.
- Chaque ligne stockée doit porter un **statut explicite** (`provisoire`, `révisé`, `consolidé`) — ce principe, déjà identifié dans le fichier Excel de l'OC (champ technique `Statut_Arret`), doit être repris dans le modèle de données final (Étape 6).
- Le schéma pivot exact (noms de colonnes définitifs) n'est pas encore figé à ce stade — il sera formalisé lors de la conception du modèle de données (Étape 6).

---

## 7. Statut de validation

- [ ] Le schéma en couches a été relu et compris dans son intégralité.
- [ ] La distinction entre Transformation et Nettoyage est claire.
- [ ] Le rôle isolé de la couche Fusion & Historisation est compris.
- [ ] Ce document est validé comme référence d'architecture pour la suite du projet.
