"""
Transformation robuste des PDF de livraisons de ciment.

Objectifs :
- gérer plusieurs formats de PDF de 2018 à 2026 ;
- extraire les données depuis le texte et les tableaux ;
- reconnaître différents séparateurs de milliers/décimales ;
- éviter les erreurs du type 1.038 au lieu de 1 038 250 ;
- éviter les années et pourcentages pris pour des livraisons ;
- comparer plusieurs candidats et choisir uniquement une valeur fiable ;
- refuser les formats inconnus ;
- produire un diagnostic détaillé ;
- ne jamais ajouter une donnée douteuse à l'historique.

Sortie principale :
    data/historique_ciment.csv

Colonnes :
    mois
    annee
    livraisons_mois
    cumul_annee
    livraisons_mois_precedent
    cumul_precedent
    fichier_source
    methode_extraction
    confiance
"""

from __future__ import annotations

import csv
import math
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import pdfplumber

# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

PDF_DIR = BASE_DIR / "data" / "pdf"
OUTPUT_FILE = BASE_DIR / "data" / "historique_ciment.csv"
ANALYSIS_DIR = BASE_DIR / "data" / "pdf_a_analyser"

OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# MOIS
# ============================================================

MOIS = {
    "janvier": 1,
    "jan": 1,

    "février": 2,
    "fevrier": 2,
    "févr": 2,
    "fevr": 2,
    "fevrier": 2,
    "february": 2,

    "mars": 3,

    "avril": 4,
    "avr": 4,

    "mai": 5,

    "juin": 6,

    "juillet": 7,
    "juil": 7,

    "août": 8,
    "aout": 8,
    "aou": 8,

    "septembre": 9,
    "sept": 9,
    "sep": 9,

    "octobre": 10,
    "oct": 10,

    "novembre": 11,
    "nov": 11,

    "décembre": 12,
    "decembre": 12,
    "dec": 12,
    "déc": 12,
}

MOIS_NOMS = {
    1: "Janvier",
    2: "Février",
    3: "Mars",
    4: "Avril",
    5: "Mai",
    6: "Juin",
    7: "Juillet",
    8: "Août",
    9: "Septembre",
    10: "Octobre",
    11: "Novembre",
    12: "Décembre",
}

# ============================================================
# DATACLASS
# ============================================================

@dataclass
class Candidate:
    mois: int
    annee: int

    livraisons_mois: float
    cumul_annee: Optional[float]

    livraisons_mois_precedent: Optional[float]
    cumul_precedent: Optional[float]

    methode: str
    confiance: int

    source_text: str = ""

# ============================================================
# UTILITAIRES
# ============================================================

def clean_text(text: str) -> str:
    """Nettoie légèrement le texte extrait du PDF."""

    if not text:
        return ""

    text = text.replace("\xa0", " ")
    text = text.replace("\u202f", " ")
    text = text.replace("\r", "\n")

    # Ligatures / caractères parasites courants.
    text = text.replace("ﬁ", "fi")
    text = text.replace("ﬂ", "fl")

    # Espaces multiples.
    text = re.sub(r"[ \t]+", " ", text)

    return text

def normalize_month_text(text: str) -> str:
    """Normalise les accents pour faciliter la recherche."""

    text = text.lower().strip()

    replacements = {
        "é": "e",
        "è": "e",
        "ê": "e",
        "ë": "e",
        "à": "a",
        "â": "a",
        "ä": "a",
        "î": "i",
        "ï": "i",
        "ô": "o",
        "ö": "o",
        "ù": "u",
        "û": "u",
        "ü": "u",
        "ç": "c",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text

def month_from_text(text: str) -> Optional[int]:
    """
    Recherche un mois dans un texte.
    """

    normalized = normalize_month_text(text)

    # On cherche d'abord les noms longs.
    ordered = sorted(MOIS.items(), key=lambda x: len(x[0]), reverse=True)

    for month_name, month_number in ordered:
        name = normalize_month_text(month_name)

        if re.search(
            rf"(?<![a-z]){re.escape(name)}(?![a-z])",
            normalized,
            flags=re.IGNORECASE,
        ):
            return month_number

    return None

def year_candidates(text: str) -> list[int]:
    """Retourne les années plausibles présentes dans un texte."""

    years = []

    for match in re.findall(r"(?<!\d)(20(?:18|19|20|21|22|23|24|25|26))(?!\d)", text):
        year = int(match)

        if year not in years:
            years.append(year)

    return years

def year_from_filename(filename: str) -> Optional[int]:
    years = year_candidates(filename)

    if not years:
        return None

    # Si plusieurs années apparaissent, prendre la première.
    return years[0]

# ============================================================
# NORMALISATION DES NOMBRES
# ============================================================

def convertir_nombre(value: str) -> Optional[float]:
    """
    Convertit différents formats numériques.

    Exemples acceptés :

        1 354 777,60
        1 354 777
        1.354.777,60
        1354777,60
        1354777.60
        1,354,777.60
        1,354,777
        1354777

    Attention :
        "1.038" est ambigu.

    Dans un contexte de livraison de ciment, il ne doit pas
    être automatiquement transformé en 1.038 tonne.
    """

    if value is None:
        return None

    s = str(value).strip()

    if not s:
        return None

    # Suppression des caractères non numériques,
    # mais conservation des séparateurs.
    s = s.replace("\xa0", " ")
    s = s.replace("\u202f", " ")

    # Tirets / symboles.
    s = s.replace("−", "-")

    negative = s.startswith("-")

    s = s.replace("-", "")

    # Enlever espaces.
    s = s.replace(" ", "")

    if not s:
        return None

    # Cas avec point ET virgule.
    if "." in s and "," in s:

        # Le dernier séparateur est normalement le séparateur décimal.
        if s.rfind(",") > s.rfind("."):
            # 1.354.777,60
            s = s.replace(".", "")
            s = s.replace(",", ".")
        else:
            # 1,354,777.60
            s = s.replace(",", "")

    # Plusieurs virgules.
    elif s.count(",") > 1:

        # 1,354,777
        parts = s.split(",")

        if all(part.isdigit() for part in parts):
            s = "".join(parts)

    # Plusieurs points.
    elif s.count(".") > 1:

        # 1.354.777
        parts = s.split(".")

        if all(part.isdigit() for part in parts):
            s = "".join(parts)

    # Une seule virgule.
    elif "," in s:

        left, right = s.split(",", 1)

        # 1,60 -> décimal
        if len(right) <= 2:
            s = left + "." + right

        # 1,354 -> dans ce contexte peut être un millier.
        elif len(right) == 3 and len(left) <= 3:
            s = left + right

        else:
            s = left + right

    # Un seul point.
    elif "." in s:

        left, right = s.split(".", 1)

        # Exemple 1354777.60
        if len(right) <= 2:
            pass

        # Exemple 1.354. Impossible ici car plusieurs points.
        # Exemple "1.038" est volontairement interprété
        # comme ambigu ailleurs.
        else:
            if len(right) == 3 and len(left) <= 3:
                s = left + right

    try:
        result = float(s)

        if negative:
            result *= -1

        if not math.isfinite(result):
            return None

        return result

    except ValueError:
        return None

def nombre_tokens(text: str) -> list[str]:
    """
    Extrait les tokens numériques en conservant les séparateurs.

    Important :
    on ne convertit pas directement ici afin de pouvoir appliquer
    des règles de contexte.
    """

    pattern = re.compile(
        r"""
        (?<!\w)
        (?:
            \d{1,3}(?:[ \u00a0\u202f.]\d{3})+(?:,\d{1,2})?
            |
            \d{1,3}(?:[ \u00a0\u00a0\u202f,]\d{3})+(?:\.\d{1,2})?
            |
            \d+(?:[.,]\d+)?
        )
        (?!\w)
        """,
        flags=re.VERBOSE,
    )

    return pattern.findall(text)

# ============================================================
# VALIDATION DES NOMBRES
# ============================================================

def est_annee(value: float) -> bool:
    return 2010 <= value <= 2035 and float(value).is_integer()

def est_pourcentage(value: float) -> bool:
    return -100 <= value <= 100

def est_valeur_ciment_plausible(value: Optional[float]) -> bool:
    """
    Livraison mensuelle nationale plausible.

    On utilise une plage large afin de ne pas casser le pipeline
    si les volumes évoluent dans le futur.

    Mais on rejette explicitement les valeurs minuscules comme
    1.038 ou 1.17.
    """

    if value is None:
        return False

    # Valeurs négatives impossibles.
    if value <= 0:
        return False

    # Une livraison nationale de ciment exprimée en tonnes
    # doit être dans cet ordre de grandeur.
    #
    # Seuil volontairement large :
    # 100 000 -> 5 000 000 tonnes.
    if value < 100_000:
        return False

    if value > 10_000_000:
        return False

    return True

def corriger_token_ciment(token: str) -> Optional[float]:
    """
    Convertit un token numérique en tenant compte du contexte
    propre aux livraisons de ciment.

    Cas critique :
        "1.038"

    On ne doit PAS obtenir 1.038 tonnes.

    On considère ici qu'un nombre avec un seul point et 3 chiffres
    après le point, lorsque sa partie gauche est <= 3 chiffres,
    peut représenter un séparateur de milliers.

    Ainsi :
        1.038 -> 1038

    mais cette valeur reste rejetée par la validation métier
    (< 100 000).

    Pour :
        1.354.777
    convertir_nombre donne 1 354 777.
    """

    value = convertir_nombre(token)

    if value is None:
        return None

    if est_annee(value):
        return None

    if est_pourcentage(value):
        return None

    return value

# ============================================================
# EXTRACTION PDF
# ============================================================

def extraire_pages(pdf_path: Path) -> tuple[str, list[list[list[str]]]]:
    """
    Extrait :
        - tout le texte ;
        - les tableaux.

    Retourne :
        (texte_complet, tables)
    """

    textes = []
    tables = []

    with pdfplumber.open(pdf_path) as pdf:

        for page in pdf.pages:

            text = page.extract_text() or ""

            if text:
                textes.append(text)

            # Extraction de tableaux.
            try:
                page_tables = page.extract_tables()

                if page_tables:
                    tables.extend(page_tables)

            except Exception:
                pass

    full_text = "\n".join(textes)

    return clean_text(full_text), tables

# ============================================================
# IDENTIFICATION MOIS / ANNÉE
# ============================================================

def identifier_periode(
    pdf_path: Path,
    text: str,
) -> tuple[Optional[int], Optional[int]]:
    """
    Identifie la période.

    Priorité :
        1. nom du fichier ;
        2. texte du PDF.
    """

    filename = pdf_path.name

    month = month_from_text(filename)
    year = year_from_filename(filename)

    # Le nom de certains fichiers peut contenir une mauvaise
    # année (exemple ancien PDF réutilisé).
    # Si le texte donne une période claire, on pourra la privilégier.
    if month is None:
        month = month_from_text(text)

    if year is None:
        years = year_candidates(text)

        if len(years) == 1:
            year = years[0]

    return month, year

# ============================================================
# RECHERCHE DES LIGNES "LIVRAISONS"
# ============================================================

def lignes_interessantes(text: str) -> list[str]:
    """
    Recherche toutes les lignes susceptibles de contenir
    les indicateurs de livraison.
    """

    lignes = []

    for raw_line in text.splitlines():

        line = clean_text(raw_line)

        normalized = normalize_month_text(line)

        keywords = [
            "livraisons en tonnes",
            "livraison en tonnes",
            "livraisons en tonne",
            "livraison en tonne",
            "livraisons",
            "livraison",
        ]

        if any(keyword in normalized for keyword in keywords):
            lignes.append(line)

    return lignes

# ============================================================
# EXTRACTION DE CANDIDATS À PARTIR D'UNE LIGNE
# ============================================================

def extraire_nombres_valides(line: str) -> list[float]:
    """
    Extrait uniquement les nombres plausibles pour des tonnes.

    Les années et pourcentages sont ignorés.
    """

    resultats = []

    for token in nombre_tokens(line):

        value = corriger_token_ciment(token)

        if value is None:
            continue

        if est_valeur_ciment_plausible(value):
            resultats.append(value)

    return resultats

def candidate_depuis_ligne(
    line: str,
    mois: int,
    annee: int,
) -> Optional[Candidate]:
    """
    Transforme une ligne "Livraisons en tonnes ..." en candidat.

    Structure habituelle :

        mois
        cumul année
        mois précédent
        cumul précédent
        %
        %

    Exemple :

        Livraisons en tonnes
        1 354 777,60
        11 399 887
        1 208 351
        11 009 608
        12,12%
        3,54%
    """

    values = extraire_nombres_valides(line)

    if not values:
        return None

    # Il faut au minimum la livraison du mois.
    liv_mois = values[0]

    cumul = values[1] if len(values) >= 2 else None
    precedent = values[2] if len(values) >= 3 else None
    cumul_precedent = values[3] if len(values) >= 4 else None

    confiance = 75

    if len(values) >= 4:
        confiance = 95

    # Validation du cumul.
    if cumul is not None:

        if cumul < liv_mois:
            # Impossible dans un cumul annuel normal.
            return None

    # Validation du cumul précédent.
    if (
        precedent is not None
        and cumul_precedent is not None
        and cumul_precedent < precedent
    ):
        # Peut arriver dans des anciens documents où la colonne
        # a été mal extraite. Dans ce cas, on rejette le candidat
        # plutôt que de contaminer l'historique.
        return None

    return Candidate(
        mois=mois,
        annee=annee,
        livraisons_mois=liv_mois,
        cumul_annee=cumul,
        livraisons_mois_precedent=precedent,
        cumul_precedent=cumul_precedent,
        methode="ligne_texte",
        confiance=confiance,
        source_text=line,
    )

# ============================================================
# EXTRACTION TABLEAUX
# ============================================================

def nettoyer_cellule(cell) -> str:
    if cell is None:
        return ""

    return clean_text(str(cell))

def table_to_lines(table) -> list[str]:
    """
    Transforme une table PDF en lignes textuelles.
    """

    lines = []

    for row in table:

        if not row:
            continue

        cells = [
            nettoyer_cellule(cell)
            for cell in row
        ]

        cells = [
            cell for cell in cells if cell
        ]

        if not cells:
            continue

        lines.append(" ".join(cells))

    return lines

def candidats_depuis_tables(
    tables,
    mois: int,
    annee: int,
) -> list[Candidate]:

    candidats = []

    for table in tables:

        lines = table_to_lines(table)

        for line in lines:

            normalized = normalize_month_text(line)

            if "livraison" not in normalized:
                continue

            values = extraire_nombres_valides(line)

            if not values:
                continue

            candidate = candidate_depuis_ligne(
                line,
                mois,
                annee,
            )

            if candidate:

                candidate.methode = "table_ligne"

                candidats.append(candidate)

    return candidats

# ============================================================
# EXTRACTION GLOBALE
# ============================================================

def extraire_candidats(
    pdf_path: Path,
    text: str,
    tables,
) -> list[Candidate]:

    mois, annee = identifier_periode(
        pdf_path,
        text,
    )

    if mois is None or annee is None:
        return []

    candidats = []

    # --------------------------------------------------------
    # STRATÉGIE 1 : lignes texte
    # --------------------------------------------------------

    for line in lignes_interessantes(text):

        candidate = candidate_depuis_ligne(
            line,
            mois,
            annee,
        )

        if candidate:
            candidats.append(candidate)

    # --------------------------------------------------------
    # STRATÉGIE 2 : tableaux
    # --------------------------------------------------------

    candidats.extend(
        candidats_depuis_tables(
            tables,
            mois,
            annee,
        )
    )

    return candidats

# ============================================================
# DÉDUPLICATION DES CANDIDATS
# ============================================================

def dedoublonner_candidats(
    candidats: list[Candidate],
) -> list[Candidate]:

    uniques = {}

    for candidate in candidats:

        key = (
            candidate.mois,
            candidate.annee,
            round(candidate.livraisons_mois, 2),
            round(candidate.cumul_annee or 0, 2),
        )

        if key not in uniques:
            uniques[key] = candidate

        else:
            # Garder la meilleure confiance.
            if candidate.confiance > uniques[key].confiance:
                uniques[key] = candidate

    return list(uniques.values())

# ============================================================
# CHOIX DU CANDIDAT
# ============================================================

def choisir_candidat(
    candidats: list[Candidate],
) -> tuple[Optional[Candidate], Optional[str]]:

    candidats = dedoublonner_candidats(candidats)

    if not candidats:
        return None, "Aucune extraction valide"

    # --------------------------------------------------------
    # Une seule valeur fiable.
    # --------------------------------------------------------

    if len(candidats) == 1:
        return candidats[0], None

    # --------------------------------------------------------
    # Plusieurs candidats.
    # --------------------------------------------------------

    # Regrouper par valeur mensuelle.
    groupes = {}

    for candidate in candidats:

        key = round(candidate.livraisons_mois, 2)

        groupes.setdefault(key, []).append(candidate)

    # Une seule valeur ressort malgré plusieurs méthodes.
    if len(groupes) == 1:

        meilleur = max(
            candidats,
            key=lambda c: c.confiance,
        )

        meilleur.confiance = min(
            100,
            meilleur.confiance + 5,
        )

        return meilleur, None

    # Plusieurs valeurs différentes.
    #
    # On ne choisit PAS arbitrairement.
    return (
        None,
        "Plusieurs extractions valides mais contradictoires",
    )

# ============================================================
# VALIDATION FINALE
# ============================================================

def validation_finale(
    candidate: Candidate,
) -> tuple[bool, str]:

    if candidate.annee < 2018 or candidate.annee > 2035:
        return False, "Année hors plage"

    if not 1 <= candidate.mois <= 12:
        return False, "Mois invalide"

    if not est_valeur_ciment_plausible(
        candidate.livraisons_mois
    ):
        return False, "Livraison mensuelle non plausible"

    if candidate.cumul_annee is not None:

        if not est_valeur_ciment_plausible(
            candidate.cumul_annee
        ):
            return False, "Cumul annuel non plausible"

        if candidate.cumul_annee < candidate.livraisons_mois:
            return False, "Cumul annuel inférieur à livraison mensuelle"

    if candidate.livraisons_mois_precedent is not None:

        if not est_valeur_ciment_plausible(
            candidate.livraisons_mois_precedent
        ):
            return False, "Livraison précédente non plausible"

    if candidate.cumul_precedent is not None:

        if not est_valeur_ciment_plausible(
            candidate.cumul_precedent
        ):
            return False, "Cumul précédent non plausible"

    return True, ""

# ============================================================
# TRAITEMENT D'UN PDF
# ============================================================

def traiter_pdf(pdf_path: Path):

    print(f"\n📄 {pdf_path.name}")

    try:

        text, tables = extraire_pages(pdf_path)

        if not text and not tables:
            return None, "PDF sans texte ni tableau"

        candidats = extraire_candidats(
            pdf_path,
            text,
            tables,
        )

        candidat, erreur = choisir_candidat(candidats)

        if candidat is None:
            return None, erreur

        valide, raison = validation_finale(
            candidat
        )

        if not valide:
            return None, raison

        return candidat, None

    except Exception as exc:

        return None, f"Erreur technique : {exc}"

# ============================================================
# COPIE PDF À ANALYSER
# ============================================================

def envoyer_en_analyse(
    pdf_path: Path,
    raison: str,
):

    destination = ANALYSIS_DIR / pdf_path.name

    try:

        shutil.copy2(
            pdf_path,
            destination,
        )

    except Exception:
        pass

# ============================================================
# CHARGEMENT HISTORIQUE EXISTANT
# ============================================================

COLONNES = [
    "mois",
    "annee",
    "livraisons_mois",
    "cumul_annee",
    "livraisons_mois_precedent",
    "cumul_precedent",
    "fichier_source",
    "methode_extraction",
    "confiance",
]

def charger_historique() -> list[dict]:

    if not OUTPUT_FILE.exists():
        return []

    lignes = []

    try:

        with open(
            OUTPUT_FILE,
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as f:

            reader = csv.DictReader(f)

            for row in reader:
                lignes.append(row)

    except Exception as exc:

        print(
            f"⚠️ Impossible de lire l'historique : {exc}"
        )

    return lignes

# ============================================================
# CONVERSION CANDIDAT → DICT
# ============================================================

def candidat_to_dict(
    candidate: Candidate,
    filename: str,
) -> dict:

    return {
        "mois": MOIS_NOMS[candidate.mois],
        "annee": candidate.annee,

        "livraisons_mois": round(
            candidate.livraisons_mois,
            2,
        ),

        "cumul_annee": (
            round(candidate.cumul_annee, 2)
            if candidate.cumul_annee is not None
            else ""
        ),

        "livraisons_mois_precedent": (
            round(
                candidate.livraisons_mois_precedent,
                2,
            )
            if candidate.livraisons_mois_precedent is not None
            else ""
        ),

        "cumul_precedent": (
            round(
                candidate.cumul_precedent,
                2,
            )
            if candidate.cumul_precedent is not None
            else ""
        ),

        "fichier_source": filename,
        "methode_extraction": candidate.methode,
        "confiance": candidate.confiance,
    }

# ============================================================
# CLÉ D'UNE PÉRIODE
# ============================================================

def periode_key(row: dict):

    mois_nom = str(row.get("mois", ""))

    mois = month_from_text(mois_nom)

    try:
        annee = int(row.get("annee"))
    except Exception:
        annee = None

    return annee, mois

# ============================================================
# TRI CHRONOLOGIQUE
# ============================================================

def trier_historique(rows: list[dict]) -> list[dict]:

    def key(row):

        annee, mois = periode_key(row)

        return (
            annee if annee is not None else 9999,
            mois if mois is not None else 99,
        )

    return sorted(rows, key=key)

# ============================================================
# ÉCRITURE CSV
# ============================================================

def sauvegarder_historique(rows: list[dict]):

    rows = trier_historique(rows)

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=COLONNES,
        )

        writer.writeheader()

        writer.writerows(rows)

# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("TRANSFORMATION ROBUSTE DES PDF CIMENT")
    print("=" * 70)

    pdf_files = sorted(
        PDF_DIR.glob("*.pdf"),
        key=lambda p: p.name.lower(),
    )

    print()
    print(f"PDF trouvés : {len(pdf_files)}")

    if not pdf_files:

        print(
            f"❌ Aucun PDF trouvé dans : {PDF_DIR}"
        )

        return

    historique = []

    succes = 0
    formats_inconnus = 0
    erreurs_techniques = 0

    methodes = {}

    fichiers_analyse = []

    for index, pdf_path in enumerate(
        pdf_files,
        start=1,
    ):

        print(
            f"\n[{index}/{len(pdf_files)}] "
            f"{pdf_path.name}"
        )

        candidate, erreur = traiter_pdf(
            pdf_path
        )

        # ----------------------------------------------------
        # ÉCHEC
        # ----------------------------------------------------

        if candidate is None:

            if erreur and erreur.startswith(
                "Erreur technique"
            ):
                erreurs_techniques += 1

            else:
                formats_inconnus += 1

            print(
                f"⚠️ FORMAT À ANALYSER : {erreur}"
            )

            envoyer_en_analyse(
                pdf_path,
                erreur or "Inconnu",
            )

            fichiers_analyse.append(
                (pdf_path.name, erreur)
            )

            continue

        # ----------------------------------------------------
        # SUCCÈS
        # ----------------------------------------------------

        row = candidat_to_dict(
            candidate,
            pdf_path.name,
        )

        historique.append(row)

        succes += 1

        methodes[candidate.methode] = (
            methodes.get(candidate.methode, 0) + 1
        )

        print(
            f"✓ {MOIS_NOMS[candidate.mois]} "
            f"{candidate.annee} | "
            f"{candidate.livraisons_mois:,.2f} tonnes | "
            f"méthode : {candidate.methode} | "
            f"confiance : {candidate.confiance}"
        )

    # ========================================================
    # DÉDOUBLONNAGE DES PÉRIODES
    # ========================================================

    periodes = {}

    for row in historique:

        key = periode_key(row)

        # Si deux PDF correspondent à la même période,
        # on conserve celui avec la meilleure confiance.
        if key not in periodes:

            periodes[key] = row

        else:

            ancien = periodes[key]

            try:
                confiance_ancienne = int(
                    ancien.get("confiance", 0)
                )
            except Exception:
                confiance_ancienne = 0

            try:
                confiance_nouvelle = int(
                    row.get("confiance", 0)
                )
            except Exception:
                confiance_nouvelle = 0

            if confiance_nouvelle > confiance_ancienne:
                periodes[key] = row

    historique = list(periodes.values())

    # ========================================================
    # SAUVEGARDE
    # ========================================================

    if historique:

        sauvegarder_historique(
            historique
        )

    # ========================================================
    # RAPPORT
    # ========================================================

    print()
    print("=" * 70)
    print("RÉSUMÉ DE LA TRANSFORMATION")
    print("=" * 70)

    print()
    print(
        f"PDF trouvés              : {len(pdf_files)}"
    )

    print(
        f"PDF correctement extraits : {len(historique)}"
    )

    print(
        f"Formats inconnus         : {formats_inconnus}"
    )

    print(
        f"Erreurs techniques       : {erreurs_techniques}"
    )

    print()

    if methodes:

        print("Méthodes utilisées :")

        for methode, nombre in sorted(
            methodes.items()
        ):
            print(
                f"  {methode} : {nombre}"
            )

    # ========================================================
    # PDF À ANALYSER
    # ========================================================

    if fichiers_analyse:

        print()
        print("=" * 70)
        print("⚠️ PDF À ANALYSER")
        print("=" * 70)

        for filename, raison in fichiers_analyse:

            print()
            print(f"❌ {filename}")
            print(
                f"   Raison : {raison}"
            )

        print()
        print(
            f"Les fichiers ont été copiés dans :"
        )

        print(
            f"   {ANALYSIS_DIR}"
        )

    # ========================================================
    # HISTORIQUE
    # ========================================================

    print()

    if historique:

        print(
            f"Fichier : {OUTPUT_FILE}"
        )

        print(
            f"Nombre de lignes : {len(historique)}"
        )

        first = historique[0]
        last = historique[-1]

        print(
            f"Première période : "
            f"{first['mois']} {first['annee']}"
        )

        print(
            f"Dernière période : "
            f"{last['mois']} {last['annee']}"
        )

        print()
        print(
            "✓ Historique créé avec succès."
        )

    else:

        print()
        print(
            "❌ Aucune donnée fiable extraite."
        )

        print(
            "Le fichier historique n'a pas été créé."
        )

# ============================================================
# EXECUTION
# ============================================================

if __name__ == "__main__":
    main()
