import os
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
URL = "https://www.mhpv.gov.ma/fr/vente-de-ciment/"
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
    "decembre": 12}
def extraire_date_pdf(filename):
    """
    Extrait le mois et l'année depuis le nom du PDF.    Exemple :
    Evolution-des-livraisons-de-ciment-juillet-2026-Fr-et-Ar.pdf
    retourne :
    (2026, 7)
    """

    filename_lower = filename.lower()

    for mois, numero_mois in MOIS.items():

        pattern = rf"{mois}[-_ ](\d{{4}})"

        match = re.search(pattern, filename_lower)

        if match:
            annee = int(match.group(1))
            return annee, numero_mois

    return None

def extract_ciment():
    """
    Récupère tous les PDF historiques de ciment
    disponibles sur le site.
    """

    print("\n========== RECHERCHE DES PDF ==========\n")

    response = requests.get(URL)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    pdfs = []

    for link in soup.find_all("a", href=True):

        href = link["href"]

        if ".pdf" not in href.lower():
            continue

        pdf_url = urljoin(URL, href)

        filename = os.path.basename(
            pdf_url.split("?")[0]
        )

        if (
            "livraison" not in filename.lower()
            and "ciment" not in filename.lower()
        ):
            continue

        date_pdf = extraire_date_pdf(filename)

        if date_pdf is None:
            continue

        annee, mois = date_pdf

        pdfs.append({
            "url": pdf_url,
            "filename": filename,
            "annee": annee,
            "mois": mois
        })

    if not pdfs:
        raise Exception(
            "Aucun PDF de livraisons de ciment trouvé."
        )

    # Supprimer les doublons exacts
    pdfs_uniques = {}

    for pdf in pdfs:

        cle = pdf["url"]

        pdfs_uniques[cle] = pdf

    pdfs = list(pdfs_uniques.values())

    # Trier du plus ancien au plus récent
    pdfs.sort(
        key=lambda x: (x["annee"], x["mois"])
    )

    print(f"Nombre de PDF trouvés : {len(pdfs)}\n")

    print("========== PDF HISTORIQUES ==========\n")

    for pdf in pdfs:

        print(
            f"- {pdf['filename']} "
            f"({pdf['mois']:02d}/{pdf['annee']})"
        )

    # ---------------------------------
    # Téléchargement de TOUS les PDF
    # ---------------------------------

    os.makedirs("data/pdf", exist_ok=True)

    print("\n========== TÉLÉCHARGEMENT ==========\n")

    fichiers_telecharges = 0
    fichiers_deja_presents = 0

    for i, pdf in enumerate(pdfs, start=1):

        filepath = os.path.join(
            "data/pdf",
            pdf["filename"]
        )

        # Si le fichier existe déjà,
        # on ne le télécharge pas à nouveau.
        if os.path.exists(filepath):

            print(
                f"[{i}/{len(pdfs)}] "
                f"Déjà présent : {pdf['filename']}"
            )

            fichiers_deja_presents += 1

            continue

        print(
            f"[{i}/{len(pdfs)}] "
            f"Téléchargement : {pdf['filename']}"
        )

        try:

            pdf_response = requests.get(
                pdf["url"],
                timeout=30
            )

            pdf_response.raise_for_status()

            with open(filepath, "wb") as f:
                f.write(pdf_response.content)

            fichiers_telecharges += 1

            print("    ✓ Téléchargé")

        except Exception as e:

            print(
                f"    ❌ Erreur : {e}"
            )

    # ---------------------------------
    # Résumé
    # ---------------------------------

    print("\n========== RÉSUMÉ ==========\n")

    print(
        f"PDF détectés       : {len(pdfs)}"
    )

    print(
        f"Nouveaux téléchargés : "
        f"{fichiers_telecharges}"
    )

    print(
        f"Déjà présents      : "
        f"{fichiers_deja_presents}"
    )

    print(
        "\nHistorique PDF disponible dans : "
        "data/pdf"
    )

    return pdfs


if __name__ == "__main__":

    extract_ciment()