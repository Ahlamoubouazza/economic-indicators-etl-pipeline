import sys
import json
import re
import requests
import pdfplumber
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen2.5:7b"
def normaliser_nombres_pdf(texte):
    """
    Corrige les séparateurs de milliers cassés par pdfplumber.
    Exemples :
        6.206 363  -> 6.206.363
        1 .048.975 -> 1.048.975
        1 424 453  -> 1 424 453
        1.204.832  -> 1.204.832
    """
    if not texte:
        return texte
    texte = re.sub(
        r'(\d)\s+(\.)',
        r'\1\2',
        texte)
    texte = re.sub(
        r'(\d{1,3}\.\d{3})\s+(\d{3})(?!\d)',
        r'\1.\2',
        texte)
    texte = re.sub(
        r'(\d{1,3}(?:\.\d{3})+)\s+(\d{3})(?!\d)',
        r'\1.\2',
        texte)
    return texte
def convertir_nombre(valeur):
    """
    Convertit les nombres présents dans les PDF.

    Exemples :
        1.204.832,04 -> 1204832.04
        1 204 832,04 -> 1204832.04
        1.204.832 -> 1204832
        1 424 453 -> 1424453
        2,67% -> 2.67
        -0,75% -> -0.75
    """

    if valeur is None:
        return None

    valeur = str(valeur).strip()

    if not valeur:
        return None

    # --------------------------------------------------------
    # Pourcentage
    # --------------------------------------------------------

    if "%" in valeur:

        valeur = valeur.replace("%", "")
        valeur = valeur.strip()
        valeur = valeur.replace(",", ".")

        try:
            return float(valeur)
        except ValueError:
            return None

    # --------------------------------------------------------
    # Nettoyage espaces insécables
    # --------------------------------------------------------

    valeur = valeur.replace("\xa0", " ")
    valeur = valeur.strip()

    # --------------------------------------------------------
    # Nombre avec espaces entre milliers
    #
    # 1 204 832,04
    # --------------------------------------------------------

    valeur_sans_espaces = valeur.replace(" ", "")

    # --------------------------------------------------------
    # Nombre français avec virgule décimale
    #
    # 1204832,04
    # --------------------------------------------------------

    if "," in valeur_sans_espaces:

        parties = valeur_sans_espaces.split(",")

        if len(parties) == 2:

            partie_entiere = parties[0]
            partie_decimale = parties[1]

            # Une partie décimale de 1 ou 2 chiffres
            # correspond généralement à un vrai décimal.
            if len(partie_decimale) <= 2:

                try:
                    return float(
                        partie_entiere.replace(".", "")
                        + "."
                        + partie_decimale
                    )
                except ValueError:
                    return None

    # --------------------------------------------------------
    # Points comme séparateurs de milliers
    #
    # 1.204.832 -> 1204832
    # --------------------------------------------------------

    valeur_sans_points = valeur_sans_espaces.replace(".", "")

    try:

        nombre = float(valeur_sans_points)

        if nombre > 100_000_000:
            return None

        return nombre

    except ValueError:
        return None


# ============================================================
# 2. EXTRACTION GENERALE DES NOMBRES
# ============================================================

def extraire_nombres(texte):

    if not texte:
        return []
    texte = normaliser_nombres_pdf(texte)


    pattern = r"""
        -?
        \d+(?:[.,]\d+)*
        (?:\s+\d{3})*
        %?
    """

    matches = re.findall(
        pattern,
        texte,
        re.VERBOSE
    )

    nombres = []

    for match in matches:

        nombre = convertir_nombre(match)

        if nombre is not None:
            nombres.append(nombre)

    return nombres


# ============================================================
# 3. EXTRACTION ROBUSTE DES NOMBRES PROPRES
# ============================================================

def extraire_nombres_propres(texte):
    """
    Extraction destinée aux tableaux de ciment.

    Gère les deux grandes familles de PDF :

    ANCIENS PDF :
        1.204.832,04
        1.173.541,00

    PDF 2025 / 2026 :
        1 424 453
        8 226 032
        722 572

    Ignore :
        - pourcentages
        - années
        - valeurs absurdes
    """

    if not texte:
        return []

    propres = []

    # Correction des nombres mal séparés par pdfplumber
    texte = normaliser_nombres_pdf(texte)

    # ========================================================
    # ETAPE 1
    # PROTEGER / SUPPRIMER LES POURCENTAGES
    # ========================================================

    texte_sans_pourcentages = re.sub(
        r'-?\d+(?:[.,]\d+)?\s*%',
        ' ',
        texte
    )

    # ========================================================
    # ETAPE 2
    # ANCIENS NOMBRES AVEC POINTS DE MILLIERS
    #
    # 1.204.832,04
    # 1.173.541,00
    # ========================================================

    nombres_anciens = re.findall(
        r'(?<![\d.])'
        r'\d{1,3}(?:\.\d{3})+'
        r'(?:,\d+)?'
        r'(?![\d.])',
        texte_sans_pourcentages
    )

    for valeur in nombres_anciens:

        nombre = convertir_nombre(valeur)

        if nombre is None:
            continue

        # années
        if (
            nombre.is_integer()
            and 2018 <= int(nombre) <= 2026
        ):
            continue

        # valeurs absurdes
        if nombre > 100_000_000:
            continue

        propres.append(nombre)

    # ========================================================
    # ETAPE 3
    # NOMBRES AVEC ESPACES
    #
    # 1 424 453
    # 8 226 032
    # 722 572
    # ========================================================

    nombres_espaces = re.findall(
        r'(?<![\d])'
        r'\d{1,3}(?:\s+\d{3})+'
        r'(?:[.,]\d+)?'
        r'(?![\d])',
        texte_sans_pourcentages
    )

    for valeur in nombres_espaces:

        nombre = convertir_nombre(valeur)

        if nombre is None:
            continue

        if (
            nombre.is_integer()
            and 2018 <= int(nombre) <= 2026
        ):
            continue

        if nombre > 100_000_000:
            continue

        propres.append(nombre)

    # ========================================================
    # ETAPE 4
    # NOMBRES SIMPLES
    #
    # IMPORTANT :
    # On les ajoute seulement s'ils ne sont pas déjà
    # contenus dans les grands nombres.
    # ========================================================

    nombres_simples = re.findall(
        r'(?<![\d.,])'
        r'-?\d+(?:[.,]\d+)?'
        r'(?![\d.,])',
        texte_sans_pourcentages
    )

    for valeur in nombres_simples:

        nombre = convertir_nombre(valeur)

        if nombre is None:
            continue

        # années
        if (
            nombre.is_integer()
            and 2018 <= int(nombre) <= 2026
        ):
            continue

        # petits nombres : généralement numéros,
        # pourcentages mal extraits, références, etc.
        if nombre <= 0:
            continue

        # valeurs absurdes
        if nombre > 100_000_000:
            continue

        propres.append(nombre)

    # ========================================================
    # ETAPE 5
    # SUPPRESSION DES DOUBLONS
    # ========================================================

    resultat = []

    for nombre in propres:

        if nombre not in resultat:
            resultat.append(nombre)

    return resultat


# ============================================================
# 4. MOIS
# ============================================================

MOIS = {
    "janvier": 1,
    "février": 2,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "août": 8,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "décembre": 12,
    "decembre": 12,
}


# ============================================================
# 5. DETECTION PERIODE
# ============================================================

def detecter_periode(texte):
    if not texte:
        return None, None
    texte_lower = texte.lower()
    pattern_periode = (
        r"(?:fin|à\s+fin|mois\s+de|mois\s+d')\s*"
        r"(janvier|février|fevrier|mars|avril|mai|juin|"
        r"juillet|août|aout|septembre|octobre|novembre|"
        r"décembre|decembre)"
        r"\s+"
        r"(20\d{2})")
    match = re.search(
        pattern_periode,
        texte_lower,
        re.IGNORECASE)
    if match:
        mois = match.group(1).capitalize()
        annee = int(match.group(2))
        return mois, annee
    for mois_nom in MOIS:
        match = re.search(
            rf"\b{re.escape(mois_nom)}\b",
            texte_lower)
        if not match:
            continue
        mois = mois_nom.capitalize()
        zone = texte[
            max(0, match.start() - 100):
            min(len(texte), match.end() + 100)]
        annees = re.findall(
            r"\b20\d{2}\b",
            zone)
        if annees:
            for annee in annees:
                annee_int = int(annee)

                if 2010 <= annee_int <= 2100:
                    return mois, annee_int

        return mois, None

    # --------------------------------------------------------
    # Dernier recours
    # --------------------------------------------------------

    annees = re.findall(
        r"\b20\d{2}\b",
        texte
    )

    if annees:

        return None, int(annees[0])

    return None, None


# ============================================================
# 6. LECTURE PDF
# ============================================================

def lire_pdf(pdf_path):

    textes = []
    tableaux = []

    with pdfplumber.open(pdf_path) as pdf:

        for page_num, page in enumerate(
            pdf.pages,
            start=1
        ):

            # ------------------------------------------------
            # Texte
            # ------------------------------------------------

            try:

                texte = page.extract_text()

                if texte:

                    textes.append({
                        "source": "texte",
                        "page": page_num,
                        "texte": texte
                    })

            except Exception:
                pass

            # ------------------------------------------------
            # Tableaux
            # ------------------------------------------------

            try:

                tables = page.extract_tables()

                for table in tables:

                    for row in table:

                        if not row:
                            continue

                        ligne = " | ".join(
                            str(cell).strip()
                            if cell
                            else ""
                            for cell in row
                        )

                        if ligne.strip():

                            tableaux.append({
                                "source": "tableau",
                                "page": page_num,
                                "texte": ligne
                            })

            except Exception:
                pass

    return textes, tableaux


# ============================================================
# 7. RECHERCHE DES CANDIDATS
# ============================================================

def trouver_ligne_livraisons(
    textes,
    tableaux
):

    candidats = []

    # --------------------------------------------------------
    # TEXTE
    # --------------------------------------------------------

    for item in textes:

        texte = item["texte"]
        lignes = texte.splitlines()

        for i, ligne in enumerate(lignes):

            ligne_lower = ligne.lower()

            if "livraisons en tonnes" not in ligne_lower:
                continue

            contexte = "\n".join(
                lignes[i:i + 8]
            )

            candidats.append({
                "source": "texte",
                "page": item["page"],
                "ligne": ligne,
                "contexte": contexte
            })

    # --------------------------------------------------------
    # TABLEAUX
    # --------------------------------------------------------

    for item in tableaux:

        ligne = item["texte"]

        if "livraisons en tonnes" not in ligne.lower():
            continue

        candidats.append({
            "source": "tableau",
            "page": item["page"],
            "ligne": ligne,
            "contexte": ligne
        })

    return candidats


# ============================================================
# 8. EXTRACTION NOUVEAU FORMAT 2026
# ============================================================

def extraction_nouveau_format_2026(
    candidats,
    annee,
    mois
):

    # Cette fonction est STRICTEMENT réservée aux PDF 2026.
    #
    # Les PDF 2025 et antérieurs ne passent jamais ici.

    if annee != 2026:
        return None

    livraisons_2026 = None
    cumul_2026 = None
    livraisons_2025 = None
    cumul_2025 = None

    for candidat in candidats:

        ligne = candidat.get(
            "ligne",
            ""
        )

        contexte = candidat.get(
            "contexte",
            ""
        )

        texte = ligne + "\n" + contexte
        texte_lower = texte.lower()

        # ====================================================
        # 1. TABLEAU RECAPITULATIF PRINCIPAL
        # ====================================================

        if (
            "livraisons en tonnes" in texte_lower
            and "livraisons de 2026 en tonnes"
            not in texte_lower
            and "livraisons de 2025 en tonnes"
            not in texte_lower
        ):

            nombres = extraire_nombres_propres(
                ligne
            )

            # Exemple :
            #
            # 1 424 453
            # 8 226 032
            # 1 398 062
            # 8 288 358

            if len(nombres) >= 4:

                valeurs = [
                    n for n in nombres
                    if n > 100_000
                ]

                if len(valeurs) >= 4:

                    livraisons_2026 = int(
                        valeurs[0]
                    )

                    cumul_2026 = int(
                        valeurs[1]
                    )

                    livraisons_2025 = int(
                        valeurs[2]
                    )

                    cumul_2025 = int(
                        valeurs[3]
                    )

        # ====================================================
        # 2. LIVRAISONS 2026
        # ====================================================

        if "livraisons de 2026 en tonnes" in texte_lower:

            nombres = extraire_nombres_propres(
                texte
            )

            valeurs = [
                n for n in nombres
                if n > 100_000
            ]

            if valeurs:

                livraisons_2026 = int(
                    valeurs[-1]
                )

        # ====================================================
        # 3. CUMUL 2026
        # ====================================================

        if "cumul de 2026 en tonnes" in texte_lower:

            nombres = extraire_nombres_propres(
                texte
            )

            valeurs = [
                n for n in nombres
                if n > 100_000
            ]

            if valeurs:

                cumul_2026 = int(
                    valeurs[-1]
                )

        # ====================================================
        # 4. LIVRAISONS 2025
        # ====================================================

        if "livraisons de 2025 en tonnes" in texte_lower:

            nombres = extraire_nombres_propres(
                texte
            )

            valeurs = [
                n for n in nombres
                if n > 100_000
            ]

            if valeurs:

                livraisons_2025 = int(
                    valeurs[-1]
                )

        # ====================================================
        # 5. CUMUL 2025
        # ====================================================

        if "cumul de 2025 en tonnes" in texte_lower:

            nombres = extraire_nombres_propres(
                texte
            )

            valeurs = [
                n for n in nombres
                if n > 100_000
            ]

            if valeurs:

                cumul_2025 = int(
                    valeurs[-1]
                )

    # ========================================================
    # VALIDATION
    # ========================================================

    if all([
        livraisons_2026 is not None,
        cumul_2026 is not None,
        livraisons_2025 is not None,
        cumul_2025 is not None
    ]):

        print()
        print("DEBUG NOUVEAU FORMAT 2026")
        print(
            "Livraisons 2026 :",
            livraisons_2026
        )
        print(
            "Cumul 2026 :",
            cumul_2026
        )
        print(
            "Livraisons 2025 :",
            livraisons_2025
        )
        print(
            "Cumul 2025 :",
            cumul_2025
        )

        return {
            "mois": mois,
            "annee": annee,
            "livraisons_mois": livraisons_2026,
            "cumul_annee": cumul_2026,
            "livraisons_mois_precedent": livraisons_2025,
            "cumul_precedent": cumul_2025,
            "confiance": 0.98,
            "methode":
                "extraction_directe_nouveau_format",
            "statut": "OK",
            "justification":
                "Extraction directe des totaux "
                "du nouveau format des rapports "
                "ciment 2026."
        }

    return None


# ============================================================
# 9. EXTRACTION ANCIEN FORMAT
# ============================================================

def extraire_4_valeurs_principales(texte):

    """
    Cherche les 4 grandes valeurs de la ligne principale.

    Exemple janvier 2020 :

    Livraisons en tonnes
    1.204.832,04
    1.204.832,04
    1.173.541,00
    1.173.541,00
    2,67%
    2,67%

    Retour :

    [
        1204832.04,
        1204832.04,
        1173541.0,
        1173541.0
    ]
    """

    nombres = extraire_nombres_propres(
        texte
    )

    # On conserve uniquement les valeurs
    # suffisamment grandes pour être des livraisons.

    grandes_valeurs = [
        n for n in nombres
        if n > 100_000
    ]

    if len(grandes_valeurs) < 4:
        return None

    return grandes_valeurs[:4]

# ============================================================
# EXTRACTION ANCIEN FORMAT — VERSION CORRIGÉE
# ============================================================

def extraire_valeurs_principales_ancien_format(texte):
    """
    Extrait les 4 valeurs principales de la ligne
    'Livraisons en tonnes'.

    Ordre attendu :

        [0] Livraisons mois courant
        [1] Cumul année courante
        [2] Livraisons mois précédent
        [3] Cumul année précédente

    Exemple :

        Livraisons en Tonnes
        1.052.975
        6.206 363
        1.229.937
        6.506.275

    Résultat :

        [
            1052975,
            6206363,
            1229937,
            6506275
        ]
    """

    if not texte:
        return None

    # ========================================================
    # 1. SUPPRESSION DES POURCENTAGES
    # ========================================================

    texte = re.sub(
        r'-?\d+(?:[.,]\d+)?\s*%',
        ' ',
        texte
    )

    # ========================================================
    # 2. CAS TABLEAU PDF
    #
    # Exemple :
    #
    # Livraisons en Tonnes |
    # 1.052.975 |
    # 6.206 363 |
    # 1.229.937 |
    # 6.506.275 |
    #
    # ========================================================

    if "|" in texte:

        cellules = [
            cellule.strip()
            for cellule in texte.split("|")
            if cellule.strip()
        ]

        valeurs = []

        for cellule in cellules:

            # ------------------------------------------------
            # Normaliser les séparateurs cassés
            # ------------------------------------------------

            cellule = normaliser_nombres_pdf(
                cellule
            )

            # ------------------------------------------------
            # Format avec points
            #
            # 1.052.975
            # 6.206.363
            # 1.229.937
            # 6.506.275
            # ------------------------------------------------

            matches_points = re.findall(
                r'(?<![\d.])'
                r'\d{1,3}(?:\.\d{3})+'
                r'(?:,\d+)?'
                r'(?![\d.])',
                cellule
            )

            for valeur in matches_points:

                nombre = convertir_nombre(
                    valeur
                )

                if nombre is None:
                    continue

                if (
                    100_000 < nombre < 100_000_000
                ):
                    valeurs.append(
                        int(nombre)
                    )

            # ------------------------------------------------
            # Format avec espaces
            #
            # 1 052 975
            # 6 206 363
            # ------------------------------------------------

            if not matches_points:

                matches_espaces = re.findall(
                    r'(?<![\d])'
                    r'\d{1,3}(?:\s+\d{3})+'
                    r'(?:[.,]\d+)?'
                    r'(?![\d])',
                    cellule
                )

                for valeur in matches_espaces:

                    nombre = convertir_nombre(
                        valeur
                    )

                    if nombre is None:
                        continue

                    if (
                        100_000 < nombre < 100_000_000
                    ):
                        valeurs.append(
                            int(nombre)
                        )

        # ----------------------------------------------------
        # Validation
        # ----------------------------------------------------

        if len(valeurs) >= 4:

            # Les 4 premières sont les valeurs
            # du tableau principal.

            return valeurs[:4]

    # ========================================================
    # 3. CAS TEXTE PDF
    # ========================================================

    texte = normaliser_nombres_pdf(
        texte
    )

    valeurs = []

    # --------------------------------------------------------
    # Format avec points
    # --------------------------------------------------------

    matches_points = re.findall(
        r'(?<![\d.])'
        r'\d{1,3}(?:\.\d{3})+'
        r'(?:,\d+)?'
        r'(?![\d.])',
        texte
    )

    for valeur in matches_points:

        nombre = convertir_nombre(
            valeur
        )

        if nombre is None:
            continue

        if (
            100_000 < nombre < 100_000_000
        ):
            valeurs.append(
                int(nombre)
            )

    # --------------------------------------------------------
    # Format avec espaces
    # --------------------------------------------------------

    matches_espaces = re.findall(
        r'(?<![\d])'
        r'\d{1,3}(?:\s+\d{3})+'
        r'(?:[.,]\d+)?'
        r'(?![\d])',
        texte
    )

    for valeur in matches_espaces:

        nombre = convertir_nombre(
            valeur
        )

        if nombre is None:
            continue

        if (
            100_000 < nombre < 100_000_000
        ):
            valeurs.append(
                int(nombre)
            )

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    if len(valeurs) >= 4:
        return valeurs[:4]

    return None


# ============================================================
# EXTRACTION DIRECTE ANCIEN FORMAT — CORRIGÉE
# ============================================================


def extraction_directe(candidat, annee, mois=None):

    """
    Extraction déterministe des anciens PDF.

    CORRECTION IMPORTANTE :
    on utilise UNIQUEMENT la ligne 'Livraisons en tonnes'.

    On n'utilise plus 'contexte', car le contexte contient
    les données régionales qui peuvent être confondues
    avec les valeurs principales.
    """

    # --------------------------------------------------------
    # IMPORTANT :
    # utiliser la ligne seulement
    # --------------------------------------------------------

    texte = candidat.get(
        "ligne",
        ""
    )

    valeurs = extraire_valeurs_principales_ancien_format(
        texte
    )

    print()
    print("DEBUG ANCIEN FORMAT CORRIGÉ")
    print("LIGNE :", texte)
    print("VALEURS PRINCIPALES :", valeurs)

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    if valeurs is None:
        return None

    if len(valeurs) < 4:
        return None

    # --------------------------------------------------------
    # Les 4 valeurs correspondent à :
    #
    # [0] mois année courante
    # [1] cumul année courante
    # [2] mois année précédente
    # [3] cumul année précédente
    # --------------------------------------------------------

    livraisons_mois = int(valeurs[0])
    cumul_annee = int(valeurs[1])
    livraisons_mois_precedent = int(valeurs[2])
    cumul_precedent = int(valeurs[3])

    # --------------------------------------------------------
    # Validation supplémentaire
    # --------------------------------------------------------

    if not all(
        valeur > 100_000
        for valeur in [
            livraisons_mois,
            cumul_annee,
            livraisons_mois_precedent,
            cumul_precedent
        ]
    ):
        return None

    return {
        "mois": None,
        "annee": annee,

        "livraisons_mois":
            livraisons_mois,

        "cumul_annee":
            cumul_annee,

        "livraisons_mois_precedent":
            livraisons_mois_precedent,

        "cumul_precedent":
            cumul_precedent,

        "confiance":
            0.99,

        "methode":
            "extraction_directe",

        "statut":
            "OK",

        "justification":
            "Valeurs extraites directement de la "
            "ligne principale des livraisons."
    }


# ============================================================
# EXTRACTION TABLEAU ANCIEN FORMAT — CORRIGÉE
# ============================================================

def extraction_tableau(candidats, annee, mois=None):
    """
    Extraction des anciens PDF lorsque la ligne principale
    est récupérée comme tableau.

    On utilise uniquement la ligne du tableau.
    """

    for candidat in candidats:

        if candidat.get("source") != "tableau":
            continue

        ligne = candidat.get(
            "ligne",
            ""
        )

        if "livraisons en tonnes" not in ligne.lower():
            continue

        print()
        print("DEBUG EXTRACTION TABLEAU CORRIGÉ")
        print("SOURCE :", candidat["source"])
        print("LIGNE :", ligne)

        valeurs = extraire_valeurs_principales_ancien_format(
            ligne
        )

        print(
            "VALEURS PRINCIPALES :",
            valeurs
        )

        if valeurs is None:
            continue

        if len(valeurs) < 4:
            continue

        livraisons_mois = int(valeurs[0])
        cumul_annee = int(valeurs[1])
        livraisons_mois_precedent = int(valeurs[2])
        cumul_precedent = int(valeurs[3])

        if not all(
            valeur > 100_000
            for valeur in [
                livraisons_mois,
                cumul_annee,
                livraisons_mois_precedent,
                cumul_precedent
            ]
        ):
            continue

        return {
            "mois": None,
            "annee": annee,

            "livraisons_mois":
                livraisons_mois,

            "cumul_annee":
                cumul_annee,

            "livraisons_mois_precedent":
                livraisons_mois_precedent,

            "cumul_precedent":
                cumul_precedent,

            "confiance":
                0.99,

            "methode":
                "extraction_tableau",

            "statut":
                "OK",

            "justification":
                "Valeurs extraites directement du "
                "tableau principal des livraisons."
        }

    return None



# ============================================================
# 11. QWEN EN DERNIER RECOURS
# ============================================================

def analyse_qwen(
    texte,
    mois,
    annee
):

    prompt = f"""
Tu es un système expert d'extraction de données
statistiques depuis des rapports PDF de ciment.

Période :
mois = {mois}
année = {annee}

Le document peut être ancien ou nouveau.

Pour les anciens formats, extraire les quatre valeurs
principales de la ligne "Livraisons en tonnes" :

1. livraisons du mois de l'année courante
2. cumul de l'année courante
3. livraisons du mois de l'année précédente
4. cumul de l'année précédente

Pour le nouveau format 2026 :

- dernier total de "Livraisons de 2026 en tonnes"
  = livraisons du mois
- dernier total de "Cumul de 2026 en tonnes"
  = cumul année
- dernier total de "Livraisons de 2025 en tonnes"
  = mois précédent
- dernier total de "Cumul de 2025 en tonnes"
  = cumul précédent

Ignore les pourcentages, régions, segments et notes.

Retourne uniquement un JSON.

Texte :
{texte}
"""

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "stream": False,
        "format": "json"
    }

    try:

        response = requests.post(
            OLLAMA_URL,
            json=payload,
            timeout=120
        )

        response.raise_for_status()

        data = response.json()

        contenu = data[
            "message"
        ][
            "content"
        ]

        return json.loads(contenu)

    except Exception as e:

        print(
            "❌ Erreur Qwen :",
            e
        )

        return {
            "mois": mois,
            "annee": annee,
            "livraisons_mois": None,
            "cumul_annee": None,
            "livraisons_mois_precedent": None,
            "cumul_precedent": None,
            "confiance": 0.0,
            "methode": "qwen_ollama",
            "statut": "ERREUR",
            "justification": str(e)
        }


# ============================================================
# 12. VALIDATION
# ============================================================

def resultat_valide(resultat):

    if not resultat:
        return False

    valeurs = [
        resultat.get("livraisons_mois"),
        resultat.get("cumul_annee"),
        resultat.get("livraisons_mois_precedent"),
        resultat.get("cumul_precedent")
    ]

    return all(
        valeur is not None
        for valeur in valeurs
    )


# ============================================================
# 13. FONCTION PRINCIPALE
# ============================================================

def extract_ciment(pdf_path):

    print("PDF :", pdf_path)
    print("Modèle :", MODEL)
    print("URL Ollama :", OLLAMA_URL)
    print("Lecture du PDF...")

    # --------------------------------------------------------
    # Lecture PDF
    # --------------------------------------------------------

    textes, tableaux = lire_pdf(
        pdf_path
    )

    texte_complet = "\n".join(
        item["texte"]
        for item in textes
    )

    # --------------------------------------------------------
    # Détection période
    # --------------------------------------------------------

    mois, annee = detecter_periode(
        texte_complet
    )

    print(
        f"Période détectée : {mois} {annee}"
    )

    # --------------------------------------------------------
    # Candidats
    # --------------------------------------------------------

    candidats = trouver_ligne_livraisons(
        textes,
        tableaux
    )

    print(
        f"Candidats trouvés : {len(candidats)}"
    )

    # --------------------------------------------------------
    # Affichage candidats
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("CANDIDATS DÉTECTÉS")
    print("=" * 70)

    for i, candidat in enumerate(
        candidats,
        start=1
    ):

        print()
        print(
            f"--- CANDIDAT {i} ---"
        )

        print(
            "Source :",
            candidat["source"]
        )

        print(
            "Page :",
            candidat["page"]
        )

        print(
            "Ligne :",
            candidat["ligne"]
        )

        print(
            "Nombres :",
            extraire_nombres(
                candidat["ligne"]
            )
        )

        print("Contexte :")
        print(
            candidat["contexte"]
        )

    # ========================================================
    # STRATEGIE SELON L'ANNEE
    # ========================================================

    resultat = None

    # ========================================================
    # CAS 2026
    # ========================================================

    if annee == 2026:

        print()
        print(
            "FORMAT : NOUVEAU FORMAT 2026"
        )

        resultat = extraction_nouveau_format_2026(
            candidats,
            annee,
            mois
        )

    # ========================================================
    # CAS 2025 ET ANNEES ANTERIEURES
    # ========================================================

    else:

        print()
        print(
            "FORMAT : ANCIEN FORMAT"
        )

        # ----------------------------------------------------
        # 1. Tableau
        # ----------------------------------------------------

        resultat = extraction_tableau(
            candidats,
            annee,
            mois
        )

        # ----------------------------------------------------
        # 2. Texte
        # ----------------------------------------------------

        if resultat is None:

            for candidat in candidats:

                if candidat["source"] != "texte":
                    continue

                print()
                print(
                    "DEBUG EXTRACTION DIRECTE"
                )

                print(
                    "SOURCE :",
                    candidat["source"]
                )

                print(
                    "LIGNE :",
                    candidat["ligne"]
                )

                print(
                    "NOMBRES :",
                    extraire_nombres(
                        candidat["ligne"]
                    )
                )

                resultat = extraction_directe(
                    candidat,
                    annee,
                    mois
                )

                if resultat is not None:
                    break

    # ========================================================
    # QWEN UNIQUEMENT SI NECESSAIRE
    # ========================================================

    if resultat is None:

        print()
        print(
            "⚠️ Structure non résolue directement."
        )

        print(
            "→ Analyse avec Qwen 2.5 7B..."
        )

        contexte = "\n".join(
            candidat["contexte"]
            for candidat in candidats
        )

        resultat = analyse_qwen(
            contexte,
            mois,
            annee
        )

    # ========================================================
    # COMPLETER MOIS / ANNEE
    # ========================================================

    if resultat.get("mois") is None:
        resultat["mois"] = mois

    if resultat.get("annee") is None:
        resultat["annee"] = annee

    # ========================================================
    # RESULTAT FINAL
    # ========================================================

    print()
    print("=" * 70)
    print("RÉSULTAT")
    print("=" * 70)

    print(
        json.dumps(
            resultat,
            ensure_ascii=False,
            indent=4
        )
    )

    print()
    print("=" * 70)

    return resultat


# ============================================================
# 14. ALIAS POUR transform_ciment.py
# ============================================================

def extraire_ciment_avec_ia(pdf_path):

    return extract_ciment(
        pdf_path
    )


# ============================================================
# 15. MAIN
# ============================================================

if __name__ == "__main__":

    if len(sys.argv) < 2:

        print(
            "Usage : "
            "python -m src.ai.extract_ciment_ai <pdf>"
        )

        sys.exit(1)

    pdf_path = sys.argv[1]

    extract_ciment(
        pdf_path
    )