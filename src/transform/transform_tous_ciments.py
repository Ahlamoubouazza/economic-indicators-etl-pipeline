import os
import glob
import pandas as pd

from src.transform.transform_ciment import (
    extraire_mois,
    extraire_annees,
    extraire_livraisons
)

PDF_DIR = "data/pdf"
OUTPUT_FILE = "data/historique_ciment.csv"


def lire_pdf(pdf_path):
    """
    Extrait le texte des 3 premières pages du PDF.
    """

    import pdfplumber

    texte = ""

    with pdfplumber.open(pdf_path) as pdf:

        for page in pdf.pages[:3]:

            page_text = page.extract_text()

            if page_text:
                texte += "\n" + page_text

    if not texte.strip():
        raise Exception("Texte PDF vide")

    return texte


def transformer_pdf(pdf_path):
    """
    Transforme un PDF de ciment en une ligne de données.
    """

    nom = os.path.basename(pdf_path)

    texte = lire_pdf(pdf_path)

    # -----------------------------
    # Mois
    # -----------------------------

    mois = extraire_mois(texte)

    # -----------------------------
    # Années
    # -----------------------------

    annee, annee_precedente = extraire_annees(texte)

    # -----------------------------
    # Livraisons
    # -----------------------------

    (
        livraisons_mois,
        cumul_annee,
        livraisons_mois_precedent,
        cumul_precedent
    ) = extraire_livraisons(texte)

    return {
        "mois": mois,
        "annee": annee,
        "livraisons_mois": livraisons_mois,
        "cumul_annee": cumul_annee,
        "annee_precedente": annee_precedente,
        "livraisons_mois_precedent": livraisons_mois_precedent,
        "cumul_precedent": cumul_precedent,
        "source_pdf": nom
    }


def supprimer_doublons(df):
    """
    Supprime les doublons correspondant au même mois et à la même année.

    Exemple :
        mai 2025
        mai 2025 -1

    Une seule ligne est conservée.
    """

    if df.empty:
        return df

    # Trier pour avoir un ordre déterministe
    df = df.sort_values(
        by=["annee", "mois", "source_pdf"]
    ).reset_index(drop=True)

    # Détection des doublons
    doublons = df[
        df.duplicated(
            subset=["annee", "mois"],
            keep=False
        )
    ]

    if not doublons.empty:

        print("\n" + "=" * 70)
        print("DOUBLONS DÉTECTÉS")
        print("=" * 70)

        for (annee, mois), groupe in doublons.groupby(
            ["annee", "mois"]
        ):

            print(f"\n{mois} {annee} :")

            for _, ligne in groupe.iterrows():

                print(
                    f"   - {ligne['source_pdf']}"
                )

        print(
            "\nUne seule version sera conservée "
            "pour chaque mois."
        )

    # Garder une seule ligne par mois/année
    df = df.drop_duplicates(
        subset=["annee", "mois"],
        keep="last"
    )

    return df


def trier_historique(df):
    """
    Trie l'historique chronologiquement.
    """

    ordre_mois = {
        "Janvier": 1,
        "Février": 2,
        "Mars": 3,
        "Avril": 4,
        "Mai": 5,
        "Juin": 6,
        "Juillet": 7,
        "Août": 8,
        "Septembre": 9,
        "Octobre": 10,
        "Novembre": 11,
        "Décembre": 12
    }

    df["numero_mois"] = df["mois"].map(ordre_mois)

    df = df.sort_values(
        by=["annee", "numero_mois"]
    ).reset_index(drop=True)

    # Le numéro du mois ne doit pas être dans le CSV final
    df = df.drop(columns=["numero_mois"])

    return df


def main():

    print("=" * 70)
    print(" TRANSFORMATION DE TOUS LES PDF CIMENT")
    print("=" * 70)

    # --------------------------------
    # Recherche des PDF
    # --------------------------------

    pdfs = glob.glob(
        os.path.join(PDF_DIR, "*.pdf")
    )

    pdfs.sort()

    print(
        f"\nPDF trouvés : {len(pdfs)}"
    )

    if not pdfs:

        raise Exception(
            f"Aucun PDF trouvé dans : {PDF_DIR}"
        )

    # --------------------------------
    # Transformation
    # --------------------------------

    resultats = []
    erreurs = []

    print("\n" + "=" * 70)
    print("TRANSFORMATION")
    print("=" * 70)

    for i, pdf_path in enumerate(
        pdfs,
        start=1
    ):

        nom = os.path.basename(pdf_path)

        print(
            f"\n[{i}/{len(pdfs)}] {nom}"
        )

        try:

            resultat = transformer_pdf(
                pdf_path
            )

            resultats.append(resultat)

            print(
                f"   ✓ {resultat['mois']} "
                f"{resultat['annee']} | "
                f"{resultat['livraisons_mois']}"
            )

        except Exception as e:

            print(
                f"   ❌ ERREUR : {e}"
            )

            erreurs.append({
                "source_pdf": nom,
                "erreur": str(e)
            })

    # --------------------------------
    # Vérification
    # --------------------------------

    print("\n" + "=" * 70)
    print("RÉSUMÉ DE LA TRANSFORMATION")
    print("=" * 70)

    print(
        f"\nPDF trouvés       : {len(pdfs)}"
    )

    print(
        f"PDF transformés   : {len(resultats)}"
    )

    print(
        f"PDF en erreur     : {len(erreurs)}"
    )

    if erreurs:

        print(
            "\n⚠️ Certains PDF n'ont pas pu être transformés."
        )

        print("\nPDF en erreur :")

        for erreur in erreurs:

            print(
                f"   ❌ {erreur['source_pdf']}"
            )

            print(
                f"      {erreur['erreur']}"
            )

        print(
            "\nLe fichier historique ne sera pas créé "
            "tant qu'il reste des erreurs."
        )

        return

    # --------------------------------
    # DataFrame
    # --------------------------------

    df = pd.DataFrame(
        resultats
    )

    print(
        f"\nLignes avant suppression des doublons : "
        f"{len(df)}"
    )

    # --------------------------------
    # Doublons
    # --------------------------------

    df = supprimer_doublons(df)

    print(
        f"Lignes après suppression des doublons : "
        f"{len(df)}"
    )

    # --------------------------------
    # Tri chronologique
    # --------------------------------

    df = trier_historique(df)

    # --------------------------------
    # Date de collecte
    # --------------------------------

    # Ici il s'agit de la date à laquelle
    # les PDF ont été traités.
    df.insert(
        0,
        "date_collecte",
        pd.Timestamp.today().date()
    )

    # --------------------------------
    # Ordre final des colonnes
    # --------------------------------

    colonnes = [
        "date_collecte",
        "mois",
        "annee",
        "livraisons_mois",
        "cumul_annee",
        "annee_precedente",
        "livraisons_mois_precedent",
        "cumul_precedent",
        "source_pdf"
    ]

    df = df[colonnes]

    # --------------------------------
    # Création du dossier data
    # --------------------------------

    os.makedirs(
        os.path.dirname(OUTPUT_FILE),
        exist_ok=True
    )

    # --------------------------------
    # Sauvegarde
    # --------------------------------

    df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    # --------------------------------
    # Résultat final
    # --------------------------------

    print("\n" + "=" * 70)
    print("HISTORIQUE CIMENT CRÉÉ")
    print("=" * 70)

    print(
        f"\nFichier : {OUTPUT_FILE}"
    )

    print(
        f"Nombre de lignes : {len(df)}"
    )

    print(
        f"Première période : "
        f"{df.iloc[0]['mois']} "
        f"{int(df.iloc[0]['annee'])}"
    )

    print(
        f"Dernière période : "
        f"{df.iloc[-1]['mois']} "
        f"{int(df.iloc[-1]['annee'])}"
    )

    print("\nAperçu :")

    print(
        df[
            [
                "mois",
                "annee",
                "livraisons_mois",
                "cumul_annee"
            ]
        ].to_string(index=False)
    )

    print(
        "\n✓ Historique créé avec succès."
    )


if __name__ == "__main__":
    main()