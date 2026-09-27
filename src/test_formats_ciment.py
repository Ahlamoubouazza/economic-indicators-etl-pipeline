import os
import glob
import importlib

import src.transform.transform_ciment as transform_module


PDF_FOLDER = "data/pdf"


pdfs = glob.glob(
    os.path.join(PDF_FOLDER, "*.pdf")
)


print("\n========================================")
print(" TEST DU VRAI TRANSFORMATEUR CIMENT")
print("========================================\n")


success = []
errors = []


for pdf_path in pdfs:

    nom = os.path.basename(pdf_path)

    print("\n----------------------------------------")
    print(f"TEST : {nom}")
    print("----------------------------------------")

    try:

        # On indique au vrai transformateur
        # quel PDF il doit traiter
        transform_module.PDF_PATH = pdf_path

        # Exécution du vrai transformateur
        df = transform_module.transformer_ciment()

        print("\n✅ SUCCÈS")

        print(df.to_string(index=False))

        success.append(nom)

    except Exception as e:

        print("\n❌ ERREUR")

        print(e)

        errors.append(
            (nom, str(e))
        )


print("\n========================================")
print(" RÉSUMÉ FINAL")
print("========================================")

print(f"\nPDF testés     : {len(pdfs)}")
print(f"PDF réussis    : {len(success)}")
print(f"PDF en erreur  : {len(errors)}")


if errors:

    print("\n---------- PDF EN ERREUR ----------")

    for nom, erreur in errors:

        print(f"\n❌ {nom}")
        print(f"   {erreur}")


if success:

    print("\n---------- PDF RÉUSSIS ----------")

    for nom in success:

        print(f"✅ {nom}")