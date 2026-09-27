import os
import re
import glob
import json
import hashlib
from collections import Counter, defaultdict

import pdfplumber


# ============================================================
# CONFIGURATION
# ============================================================

PDF_DIR = "data/pdf"
OUTPUT_DIR = "data/diagnostic_ciment"

REPORT_JSON = os.path.join(
    OUTPUT_DIR,
    "rapport_diagnostic_ciment.json"
)

REPORT_TXT = os.path.join(
    OUTPUT_DIR,
    "rapport_diagnostic_ciment.txt"
)


# ============================================================
# MOTIFS RECHERCHÉS
# ============================================================

MOTS_CLES_LIVRAISONS = [
    "livraisons en tonnes",
    "livraisons en tonnes",
    "livraisons en tonne",
    "livraison en tonnes",
    "livraison en tonne",
    "livraisons",
    "livraison"
]

MOIS = [
    "janvier",
    "février",
    "fevrier",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "aout",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
    "decembre"
]


# ============================================================
# NORMALISATION
# ============================================================

def normaliser_texte(texte):
    """
    Normalise légèrement le texte sans modifier les nombres.
    """

    if not texte:
        return ""

    texte = texte.replace("\xa0", " ")
    texte = texte.replace("\u202f", " ")
    texte = texte.replace("\r", "\n")

    # Plusieurs espaces -> un espace
    texte = re.sub(r"[ \t]+", " ", texte)

    return texte.strip()


# ============================================================
# HASH DU PDF
# ============================================================

def calculer_hash(pdf_path):
    """
    Calcule un hash SHA256 du PDF.

    Permet de détecter plus tard si un PDF a changé.
    """

    sha256 = hashlib.sha256()

    with open(pdf_path, "rb") as f:

        while True:

            bloc = f.read(1024 * 1024)

            if not bloc:
                break

            sha256.update(bloc)

    return sha256.hexdigest()


# ============================================================
# EXTRACTION DU TEXTE
# ============================================================

def extraire_texte_pdf(pdf_path):
    """
    Extrait le texte de toutes les pages.

    On ne limite PAS à 3 pages ici :
    le diagnostic doit inspecter le PDF complet.
    """

    pages = []
    texte_complet = []

    with pdfplumber.open(pdf_path) as pdf:

        nombre_pages = len(pdf.pages)

        for numero_page, page in enumerate(
            pdf.pages,
            start=1
        ):

            texte = page.extract_text()

            if texte:

                texte = normaliser_texte(texte)

                pages.append({
                    "page": numero_page,
                    "texte": texte,
                    "longueur": len(texte)
                })

                texte_complet.append(
                    texte
                )

            else:

                pages.append({
                    "page": numero_page,
                    "texte": "",
                    "longueur": 0
                })

    return (
        nombre_pages,
        pages,
        "\n".join(texte_complet)
    )


# ============================================================
# RECHERCHE DES MOTS-CLÉS
# ============================================================

def rechercher_livraisons(pages):
    """
    Recherche toutes les lignes contenant des mots liés
    aux livraisons.
    """

    resultats = []

    for page_info in pages:

        page = page_info["page"]
        texte = page_info["texte"]

        if not texte:
            continue

        lignes = texte.split("\n")

        for numero_ligne, ligne in enumerate(
            lignes,
            start=1
        ):

            ligne_lower = ligne.lower()

            for mot in MOTS_CLES_LIVRAISONS:

                if mot in ligne_lower:

                    resultats.append({
                        "page": page,
                        "ligne": numero_ligne,
                        "mot_cle": mot,
                        "texte": ligne.strip()
                    })

                    break

    return resultats


# ============================================================
# EXTRACTION DES NOMBRES
# ============================================================

def extraire_nombres(texte):
    """
    Extrait les nombres visibles dans une ligne.

    Cette fonction est volontairement diagnostique :
    elle ne décide PAS encore si un nombre représente
    une livraison, un cumul ou un pourcentage.
    """

    if not texte:
        return []

    motif = r"""
        (?<![\w])
        [-+]?
        (?:
            \d{1,3}(?:[ .\u00a0\u202f]\d{3})+
            |
            \d+
        )
        (?:
            [,.]\d+
        )?
        (?![\w])
    """

    nombres = re.findall(
        motif,
        texte,
        flags=re.VERBOSE
    )

    return [
        n.strip()
        for n in nombres
    ]


# ============================================================
# SIGNATURE DE STRUCTURE
# ============================================================

def signature_ligne(ligne):
    """
    Transforme une ligne en signature structurelle.

    Exemple :

    Livraisons en tonnes 1 249 414,00 9 976 062,74 ...

    devient approximativement :

    TEXTE NUM TEXTE NUM NUM NUM ...

    Cela permet de regrouper les PDF similaires.
    """

    if not ligne:
        return ""

    texte = ligne.lower()

    # Nombres
    texte = re.sub(
        r"[-+]?\d[\d\s.,]*",
        " NUM ",
        texte
    )

    # Pourcentages
    texte = re.sub(
        r"NUM\s*%",
        " PCT ",
        texte
    )

    # Espaces
    texte = re.sub(
        r"\s+",
        " ",
        texte
    )

    return texte.strip()


# ============================================================
# PROFIL D'UN PDF
# ============================================================

def analyser_pdf(pdf_path):

    nom = os.path.basename(pdf_path)

    resultat = {
        "nom": nom,
        "taille_octets": os.path.getsize(pdf_path),
        "hash_sha256": None,
        "statut": "OK",
        "erreur": None,
        "nombre_pages": 0,
        "pages_avec_texte": 0,
        "longueur_texte": 0,
        "annees_trouvees": [],
        "mois_trouves": [],
        "lignes_livraisons": [],
        "nombres_lignes_livraisons": [],
        "signatures": []
    }

    # --------------------------------------------------------
    # HASH
    # --------------------------------------------------------

    try:

        resultat["hash_sha256"] = calculer_hash(
            pdf_path
        )

    except Exception as e:

        resultat["erreur"] = (
            f"Erreur hash : {e}"
        )

    # --------------------------------------------------------
    # EXTRACTION
    # --------------------------------------------------------

    try:

        (
            nombre_pages,
            pages,
            texte_complet
        ) = extraire_texte_pdf(
            pdf_path
        )

        resultat["nombre_pages"] = nombre_pages

        resultat["pages_avec_texte"] = sum(
            1
            for p in pages
            if p["texte"]
        )

        resultat["longueur_texte"] = len(
            texte_complet
        )

    except Exception as e:

        resultat["statut"] = "ERREUR"

        resultat["erreur"] = (
            f"Extraction PDF impossible : {e}"
        )

        return resultat

    # --------------------------------------------------------
    # ANNÉES
    # --------------------------------------------------------

    annees = re.findall(
        r"\b(?:19|20)\d{2}\b",
        texte_complet
    )

    resultat["annees_trouvees"] = sorted(
        set(annees)
    )

    # --------------------------------------------------------
    # MOIS
    # --------------------------------------------------------

    texte_lower = texte_complet.lower()

    mois_trouves = []

    for mois in MOIS:

        if mois in texte_lower:

            mois_trouves.append(
                mois
            )

    resultat["mois_trouves"] = sorted(
        set(mois_trouves)
    )

    # --------------------------------------------------------
    # LIGNES LIVRAISONS
    # --------------------------------------------------------

    lignes = rechercher_livraisons(
        pages
    )

    for item in lignes:

        ligne = item["texte"]

        nombres = extraire_nombres(
            ligne
        )

        signature = signature_ligne(
            ligne
        )

        resultat["lignes_livraisons"].append(
            item
        )

        resultat["nombres_lignes_livraisons"].append(
            nombres
        )

        resultat["signatures"].append(
            signature
        )

    # --------------------------------------------------------
    # DÉTECTION GLOBALE
    # --------------------------------------------------------

    if not lignes:

        resultat["statut"] = (
            "AUCUNE_LIGNE_LIVRAISON"
        )

    elif len(lignes) > 1:

        resultat["statut"] = (
            "PLUSIEURS_LIGNES_LIVRAISON"
        )

    else:

        nombres = (
            resultat[
                "nombres_lignes_livraisons"
            ][0]
        )

        if len(nombres) < 2:

            resultat["statut"] = (
                "LIGNE_LIVRAISON_SANS_ASSEZ_DE_NOMBRES"
            )

        else:

            resultat["statut"] = "OK"

    return resultat


# ============================================================
# CLASSIFICATION DES STRUCTURES
# ============================================================

def construire_signatures(rapports):

    compteur = Counter()

    pdf_par_signature = defaultdict(list)

    for rapport in rapports:

        signatures = rapport.get(
            "signatures",
            []
        )

        for signature in signatures:

            if not signature:
                continue

            compteur[signature] += 1

            pdf_par_signature[
                signature
            ].append(
                rapport["nom"]
            )

    return (
        compteur,
        pdf_par_signature
    )


# ============================================================
# ANALYSE DES NOMBRES
# ============================================================

def convertir_nombre_simple(nombre):
    """
    Conversion indicative uniquement.

    Le but ici est de repérer les formats dangereux.

    Exemples :

    1 354 777,60
    1.354.777,60
    1354777.60
    1,354,777.60
    """

    if not nombre:
        return None

    valeur = nombre.strip()

    valeur = valeur.replace(
        "\u00a0",
        " "
    )

    valeur = valeur.replace(
        "\u202f",
        " "
    )

    # Supprimer espaces
    valeur = valeur.replace(
        " ",
        ""
    )

    # Cas européen :
    # 1.354.777,60
    if (
        "." in valeur
        and "," in valeur
    ):

        if valeur.rfind(",") > valeur.rfind("."):

            valeur = valeur.replace(
                ".",
                ""
            )

            valeur = valeur.replace(
                ",",
                "."
            )

    # Plusieurs virgules :
    # 1,354,777.60
    elif valeur.count(",") > 1:

        valeur = valeur.replace(
            ",",
            ""
        )

    # Plusieurs points :
    # 1.354.777
    elif valeur.count(".") > 1:

        valeur = valeur.replace(
            ".",
            ""
        )

    # Une seule virgule
    elif "," in valeur:

        apres = valeur.split(",")[-1]

        if len(apres) == 3:

            valeur = valeur.replace(
                ",",
                ""
            )

        else:

            valeur = valeur.replace(
                ",",
                "."
            )

    try:

        return float(valeur)

    except ValueError:

        return None


def analyser_formats_numeriques(rapports):

    resultats = []

    for rapport in rapports:

        for index, nombres in enumerate(
            rapport.get(
                "nombres_lignes_livraisons",
                []
            )
        ):

            for nombre in nombres:

                valeur = convertir_nombre_simple(
                    nombre
                )

                resultats.append({
                    "pdf": rapport["nom"],
                    "ligne_index": index,
                    "nombre_original": nombre,
                    "valeur_convertie": valeur
                })

    return resultats


# ============================================================
# RAPPORT TEXTE
# ============================================================

def generer_rapport_texte(
    rapports,
    signatures,
    pdf_par_signature
):

    lignes = []

    lignes.append(
        "=" * 80
    )

    lignes.append(
        "DIAGNOSTIC COMPLET DES PDF CIMENT"
    )

    lignes.append(
        "=" * 80
    )

    lignes.append("")

    lignes.append(
        f"PDF analysés : {len(rapports)}"
    )

    lignes.append("")

    # --------------------------------------------------------
    # STATUTS
    # --------------------------------------------------------

    statuts = Counter(
        r["statut"]
        for r in rapports
    )

    lignes.append(
        "STATUTS"
    )

    lignes.append(
        "-" * 80
    )

    for statut, nombre in statuts.most_common():

        lignes.append(
            f"{statut} : {nombre}"
        )

    lignes.append("")

    # --------------------------------------------------------
    # STRUCTURES
    # --------------------------------------------------------

    lignes.append(
        "STRUCTURES DE LIGNES DE LIVRAISON"
    )

    lignes.append(
        "-" * 80
    )

    for signature, nombre in signatures.most_common():

        lignes.append(
            f"\nOccurrences : {nombre}"
        )

        lignes.append(
            f"Signature : {signature}"
        )

        exemples = pdf_par_signature[
            signature
        ][:5]

        for exemple in exemples:

            lignes.append(
                f"   - {exemple}"
            )

    lignes.append("")

    # --------------------------------------------------------
    # PDF PROBLÉMATIQUES
    # --------------------------------------------------------

    problemes = [
        r
        for r in rapports
        if r["statut"] != "OK"
    ]

    lignes.append(
        "PDF À INSPECTER"
    )

    lignes.append(
        "-" * 80
    )

    if not problemes:

        lignes.append(
            "Aucun PDF problématique."
        )

    else:

        for rapport in problemes:

            lignes.append("")

            lignes.append(
                f"❌ {rapport['nom']}"
            )

            lignes.append(
                f"   Statut : {rapport['statut']}"
            )

            if rapport["erreur"]:

                lignes.append(
                    f"   Erreur : {rapport['erreur']}"
                )

            lignes.append(
                f"   Pages : {rapport['nombre_pages']}"
            )

            lignes.append(
                f"   Pages avec texte : "
                f"{rapport['pages_avec_texte']}"
            )

            lignes.append(
                f"   Années : "
                f"{rapport['annees_trouvees']}"
            )

            lignes.append(
                f"   Mois : "
                f"{rapport['mois_trouves']}"
            )

            for ligne_info in rapport[
                "lignes_livraisons"
            ]:

                lignes.append(
                    "   Ligne trouvée :"
                )

                lignes.append(
                    f"      page={ligne_info['page']} "
                    f"ligne={ligne_info['ligne']}"
                )

                lignes.append(
                    f"      {ligne_info['texte']}"
                )

    lignes.append("")

    # --------------------------------------------------------
    # FIN
    # --------------------------------------------------------

    lignes.append(
        "=" * 80
    )

    lignes.append(
        "FIN DU DIAGNOSTIC"
    )

    lignes.append(
        "=" * 80
    )

    return "\n".join(
        lignes
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print(
        "DIAGNOSTIC COMPLET DES PDF CIMENT"
    )
    print("=" * 70)

    os.makedirs(
        OUTPUT_DIR,
        exist_ok=True
    )

    pdfs = glob.glob(
        os.path.join(
            PDF_DIR,
            "*.pdf"
        )
    )

    pdfs.sort()

    print(
        f"\nPDF trouvés : {len(pdfs)}\n"
    )

    rapports = []

    for index, pdf_path in enumerate(
        pdfs,
        start=1
    ):

        nom = os.path.basename(
            pdf_path
        )

        print(
            f"[{index}/{len(pdfs)}] {nom}"
        )

        try:

            rapport = analyser_pdf(
                pdf_path
            )

            rapports.append(
                rapport
            )

            statut = rapport["statut"]

            if statut == "OK":

                print(
                    "   ✓ Ligne livraison détectée"
                )

            else:

                print(
                    f"   ⚠ {statut}"
                )

        except Exception as e:

            rapport = {
                "nom": nom,
                "statut": "ERREUR",
                "erreur": str(e)
            }

            rapports.append(
                rapport
            )

            print(
                f"   ❌ ERREUR : {e}"
            )

    # --------------------------------------------------------
    # SIGNATURES
    # --------------------------------------------------------

    (
        signatures,
        pdf_par_signature
    ) = construire_signatures(
        rapports
    )

    # --------------------------------------------------------
    # FORMATS NUMÉRIQUES
    # --------------------------------------------------------

    formats_numeriques = (
        analyser_formats_numeriques(
            rapports
        )
    )

    # --------------------------------------------------------
    # JSON
    # --------------------------------------------------------

    rapport_global = {
        "nombre_pdf": len(pdfs),

        "statuts": dict(
            Counter(
                r["statut"]
                for r in rapports
            )
        ),

        "signatures": dict(
            signatures
        ),

        "pdf": rapports,

        "formats_numeriques":
            formats_numeriques
    }

    with open(
        REPORT_JSON,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            rapport_global,
            f,
            ensure_ascii=False,
            indent=2
        )

    # --------------------------------------------------------
    # TXT
    # --------------------------------------------------------

    rapport_texte = generer_rapport_texte(
        rapports,
        signatures,
        pdf_par_signature
    )

    with open(
        REPORT_TXT,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            rapport_texte
        )

    # --------------------------------------------------------
    # RÉSUMÉ CONSOLE
    # --------------------------------------------------------

    print("\n")
    print("=" * 70)
    print(
        "RÉSUMÉ DU DIAGNOSTIC"
    )
    print("=" * 70)

    statuts = Counter(
        r["statut"]
        for r in rapports
    )

    print(
        f"\nPDF analysés : {len(rapports)}"
    )

    print(
        f"Lignes livraison détectées : "
        f"{statuts.get('OK', 0)}"
    )

    print(
        f"PDF sans ligne livraison : "
        f"{statuts.get('AUCUNE_LIGNE_LIVRAISON', 0)}"
    )

    print(
        f"PDF avec plusieurs lignes : "
        f"{statuts.get('PLUSIEURS_LIGNES_LIVRAISON', 0)}"
    )

    print(
        f"PDF avec peu de nombres : "
        f"{statuts.get('LIGNE_LIVRAISON_SANS_ASSEZ_DE_NOMBRES', 0)}"
    )

    print(
        f"PDF en erreur : "
        f"{statuts.get('ERREUR', 0)}"
    )

    print(
        f"\nStructures différentes détectées : "
        f"{len(signatures)}"
    )

    print(
        "\nFichiers générés :"
    )

    print(
        f"  - {REPORT_JSON}"
    )

    print(
        f"  - {REPORT_TXT}"
    )

    print(
        "\n✓ Diagnostic terminé."
    )


# ============================================================
# POINT D'ENTRÉE
# ============================================================

if __name__ == "__main__":
    main()