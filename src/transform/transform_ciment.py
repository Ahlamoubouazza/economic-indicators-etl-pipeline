
import os
import sys
import shutil

from src.ai.extract_ciment_ai import extract_ciment


# ============================================================
# CONFIGURATION
# ============================================================

PDF_DIR = "data/pdf"
PDF_A_ANALYSER = "data/pdf_a_analyser"


# ============================================================
# ANALYSE D'UN PDF
# ============================================================

def analyser_pdf(pdf_path):
    """
    Analyse un seul PDF avec le module IA.

    extract_ciment() retourne directement
    le dictionnaire final extrait du PDF.
    """

    print()
    print("=" * 70)
    print("ANALYSE DU PDF")
    print("=" * 70)

    print("Fichier :", os.path.basename(pdf_path))

    try:
        resultat = extract_ciment(pdf_path)

    except Exception as e:

        print()
        print("❌ ERREUR pendant l'extraction")
        print("Erreur :", e)

        return None

    # --------------------------------------------------------
    # Vérification
    # --------------------------------------------------------

    if not resultat:
        print()
        print("❌ Aucun résultat obtenu.")

        return None

    # --------------------------------------------------------
    # Affichage
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("RÉSULTAT TRANSFORMÉ")
    print("=" * 70)

    for key, value in resultat.items():
        print(f"{key} : {value}")

    # --------------------------------------------------------
    # Vérification du statut
    # --------------------------------------------------------

    statut = resultat.get("statut")

    if statut == "OK":

        print()
        print("✅ PDF correctement extrait.")

        return resultat

    elif statut == "PARTIEL":

        print()
        print("⚠️ Extraction partielle.")

        # On conserve quand même le résultat.
        return resultat

    else:

        print()
        print("❌ Extraction non valide.")

        envoyer_pdf_a_verifier(pdf_path)

        return None


# ============================================================
# ENVOYER UN PDF À VÉRIFIER
# ============================================================

def envoyer_pdf_a_verifier(pdf_path):

    os.makedirs(
        PDF_A_ANALYSER,
        exist_ok=True
    )

    destination = os.path.join(
        PDF_A_ANALYSER,
        os.path.basename(pdf_path)
    )

    try:

        shutil.copy2(
            pdf_path,
            destination
        )

        print()
        print("📁 PDF envoyé dans :")
        print(destination)

    except Exception as e:

        print()
        print("⚠️ Impossible de copier le PDF.")
        print("Erreur :", e)


# ============================================================
# TRAITEMENT D'UN PDF FOURNI EN ARGUMENT
# ============================================================

def traiter_pdf_unique(pdf_path):

    if not os.path.exists(pdf_path):

        print()
        print("❌ PDF introuvable :")
        print(pdf_path)

        return

    if not pdf_path.lower().endswith(".pdf"):

        print()
        print("❌ Le fichier fourni n'est pas un PDF.")

        return

    analyser_pdf(pdf_path)


# ============================================================
# TRAITEMENT DE TOUS LES PDF
# ============================================================

def traiter_tous_les_pdfs():

    if not os.path.exists(PDF_DIR):

        print()
        print("❌ Dossier introuvable :")
        print(PDF_DIR)

        return

    pdfs = [
        f
        for f in os.listdir(PDF_DIR)
        if f.lower().endswith(".pdf")
    ]

    # --------------------------------------------------------
    # Aucun PDF
    # --------------------------------------------------------

    if not pdfs:

        print()
        print("⚠️ Aucun PDF trouvé dans :")
        print(PDF_DIR)

        return

    # --------------------------------------------------------
    # Informations
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("PIPELINE CIMENT")
    print("=" * 70)

    print()
    print("Dossier :", PDF_DIR)
    print("PDF trouvés :", len(pdfs))

    # --------------------------------------------------------
    # Traitement
    # --------------------------------------------------------

    resultats = []

    for index, pdf in enumerate(pdfs, start=1):

        print()
        print()
        print("#" * 70)
        print(
            f"[{index}/{len(pdfs)}] {pdf}"
        )
        print("#" * 70)

        chemin = os.path.join(
            PDF_DIR,
            pdf
        )

        resultat = analyser_pdf(chemin)

        if resultat is not None:

            resultats.append(
                {
                    "fichier": pdf,
                    **resultat
                }
            )

    # --------------------------------------------------------
    # Résumé
    # --------------------------------------------------------

    print()
    print()
    print("=" * 70)
    print("RÉSUMÉ DU TRAITEMENT")
    print("=" * 70)

    print()
    print("PDF trouvés :", len(pdfs))

    print(
        "PDF traités :",
        len(resultats)
    )

    print(
        "PDF non traités :",
        len(pdfs) - len(resultats)
    )

    # --------------------------------------------------------
    # Résultats
    # --------------------------------------------------------

    if resultats:

        print()
        print("=" * 70)
        print("DONNÉES EXTRAITES")
        print("=" * 70)

        for resultat in resultats:

            print()
            print(
                "📄",
                resultat.get("fichier")
            )

            print(
                "   Mois :",
                resultat.get("mois")
            )

            print(
                "   Année :",
                resultat.get("annee")
            )

            print(
                "   Livraison mois :",
                resultat.get("livraisons_mois")
            )

            print(
                "   Cumul année :",
                resultat.get("cumul_annee")
            )

            print(
                "   Livraison mois précédent :",
                resultat.get(
                    "livraisons_mois_precedent"
                )
            )

            print(
                "   Cumul précédent :",
                resultat.get(
                    "cumul_precedent"
                )

            )

            print(
                "   Méthode :",
                resultat.get("methode")
            )

            print(
                "   Statut :",
                resultat.get("statut")
            )

    else:

        print()
        print("⚠️ Aucun résultat exploitable.")


# ============================================================
# MAIN
# ============================================================

def main():

    # --------------------------------------------------------
    # Cas 1 :
    # un PDF est fourni en argument
    #
    # Exemple :
    #
    # python -m src.transform.transform_ciment \
    # "data/pdf/mon_fichier.pdf"
    # --------------------------------------------------------

    if len(sys.argv) >= 2:

        pdf_path = sys.argv[1]

        traiter_pdf_unique(
            pdf_path
        )

        return

    # --------------------------------------------------------
    # Cas 2 :
    # aucun argument
    #
    # On traite tous les PDF de data/pdf
    # --------------------------------------------------------

    traiter_tous_les_pdfs()


# ============================================================
# EXECUTION
# ============================================================

if __name__ == "__main__":

    main()
