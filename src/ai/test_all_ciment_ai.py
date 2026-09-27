import os
import json
from pathlib import Path

from src.ai.extract_ciment_ai import extraire_ciment_avec_ia


PDF_DIR = Path("data/pdf")
RESULT_FILE = Path("data/resultats_ia_ciment.json")


def main():

    print("=" * 70)
    print("TEST IA DE TOUS LES PDF CIMENT")
    print("=" * 70)

    pdfs = sorted(PDF_DIR.glob("*.pdf"))

    print(f"\nPDF trouvés : {len(pdfs)}\n")

    resultats = []

    ok = 0
    a_verifier = 0
    echec = 0

    for i, pdf in enumerate(pdfs, 1):

        print("-" * 70)
        print(f"[{i}/{len(pdfs)}] {pdf.name}")

        try:

            resultat = extraire_ciment_avec_ia(str(pdf))

            if resultat.get("success"):

                data = resultat.get("data", {})

                statut = data.get("statut")

                if statut == "OK":
                    print("✅ OK")
                    ok += 1

                else:
                    print(f"⚠️ {statut}")
                    a_verifier += 1

            else:

                print("❌ ÉCHEC")
                print(resultat.get("reason"))

                echec += 1

            resultats.append({
                "pdf": pdf.name,
                "resultat": resultat
            })

        except Exception as e:

            print(f"❌ ERREUR : {e}")

            echec += 1

            resultats.append({
                "pdf": pdf.name,
                "resultat": {
                    "success": False,
                    "reason": str(e)
                }
            })

    with open(
        RESULT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            resultats,
            f,
            ensure_ascii=False,
            indent=4
        )

    print("\n")
    print("=" * 70)
    print("RÉSUMÉ")
    print("=" * 70)

    print(f"PDF trouvés       : {len(pdfs)}")
    print(f"✅ OK              : {ok}")
    print(f"⚠️ À vérifier      : {a_verifier}")
    print(f"❌ Échecs          : {echec}")

    print("\nRésultats sauvegardés dans :")
    print(RESULT_FILE)


if __name__ == "__main__":
    main()