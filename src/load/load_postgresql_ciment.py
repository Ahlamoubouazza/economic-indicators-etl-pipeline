import pandas as pd
import psycopg2
import os
from dotenv import load_dotenv


# ============================================================
# Chargement des variables d'environnement
# ============================================================

load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

HISTORICAL_FILE = "data/historique_ciment.csv"


# ============================================================
# Connexion PostgreSQL
# ============================================================

def get_connection():

    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )


# ============================================================
# Chargement des données CIMENT
# ============================================================

def load_ciment():

    # --------------------------------------------------------
    # Lecture de l'historique
    # --------------------------------------------------------

    df = pd.read_csv(
        HISTORICAL_FILE,
        encoding="utf-8-sig"
    )

    if df.empty:
        print("Aucune donnée CIMENT à charger.")
        return

    # --------------------------------------------------------
    # Connexion
    # --------------------------------------------------------

    conn = get_connection()
    cursor = conn.cursor()

    try:

        for _, row in df.iterrows():

            # ------------------------------------------------
            # Source CIMENT
            # ------------------------------------------------

            cursor.execute(
                """
                SELECT id
                FROM dim_source
                WHERE code = 'CIMENT'
                """
            )

            source_result = cursor.fetchone()

            if source_result is None:
                raise Exception(
                    "La source CIMENT n'existe pas dans dim_source."
                )

            source_id = source_result[0]

            # ------------------------------------------------
            # Indicateur CIMENT_MOIS
            # ------------------------------------------------

            cursor.execute(
                """
                SELECT id
                FROM dim_indicateur
                WHERE code = 'CIMENT_MOIS'
                """
            )

            indicateur_mois_result = cursor.fetchone()

            if indicateur_mois_result is None:
                raise Exception(
                    "L'indicateur CIMENT_MOIS n'existe pas."
                )

            indicateur_mois_id = indicateur_mois_result[0]

            # ------------------------------------------------
            # Indicateur CIMENT_CUMUL
            # ------------------------------------------------

            cursor.execute(
                """
                SELECT id
                FROM dim_indicateur
                WHERE code = 'CIMENT_CUMUL'
                """
            )

            indicateur_cumul_result = cursor.fetchone()

            if indicateur_cumul_result is None:
                raise Exception(
                    "L'indicateur CIMENT_CUMUL n'existe pas."
                )

            indicateur_cumul_id = indicateur_cumul_result[0]

            # ------------------------------------------------
            # Recherche de la période
            #
            # Pour le ciment, la période correspond au mois
            # publié dans le PDF.
            # ------------------------------------------------

            annee = int(row["annee"])
            mois = row["mois"]

            mois_mapping = {
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

            mois_numero = mois_mapping[mois]

            cursor.execute(
                """
                SELECT id
                FROM dim_periode
                WHERE annee = %s
                AND mois = %s
                """,
                (annee, mois_numero)
            )

            periode_result = cursor.fetchone()

            if periode_result is None:
                raise Exception(
                    f"Aucune période trouvée pour "
                    f"{mois} {annee}."
                )

            periode_id = periode_result[0]

            # ------------------------------------------------
            # Vérifier si CIMENT_MOIS existe déjà
            # ------------------------------------------------

            cursor.execute(
                """
                SELECT id
                FROM fait_indicateur_valeur
                WHERE indicateur_id = %s
                AND periode_id = %s
                AND source_id = %s
                AND segment_id IS NULL
                AND est_courante = TRUE
                """,
                (
                    indicateur_mois_id,
                    periode_id,
                    source_id
                )
            )

            existe_mois = cursor.fetchone()

            # ------------------------------------------------
            # Insertion CIMENT_MOIS
            # ------------------------------------------------

            if existe_mois is None:

                cursor.execute(
                    """
                    INSERT INTO fait_indicateur_valeur (
                        indicateur_id,
                        periode_id,
                        source_id,
                        segment_id,
                        valeur,
                        statut,
                        date_extraction,
                        valide_depuis,
                        valide_jusqu_a,
                        est_courante
                    )
                    VALUES (
                        %s,
                        %s,
                        %s,
                        NULL,
                        %s,
                        'consolide',
                        NOW(),
                        NOW(),
                        NULL,
                        TRUE
                    )
                    """,
                    (
                        indicateur_mois_id,
                        periode_id,
                        source_id,
                        float(row["livraisons_mois"])
                    )
                )

                print(
                    f"✅ CIMENT_MOIS inséré : "
                    f"{row['livraisons_mois']} tonnes"
                )

            else:

                print(
                    "⏭️ CIMENT_MOIS déjà présent."
                )

            # ------------------------------------------------
            # Vérifier si CIMENT_CUMUL existe déjà
            # ------------------------------------------------

            cursor.execute(
                """
                SELECT id
                FROM fait_indicateur_valeur
                WHERE indicateur_id = %s
                AND periode_id = %s
                AND source_id = %s
                AND segment_id IS NULL
                AND est_courante = TRUE
                """,
                (
                    indicateur_cumul_id,
                    periode_id,
                    source_id
                )
            )

            existe_cumul = cursor.fetchone()

            # ------------------------------------------------
            # Insertion CIMENT_CUMUL
            # ------------------------------------------------

            if existe_cumul is None:

                cursor.execute(
                    """
                    INSERT INTO fait_indicateur_valeur (
                        indicateur_id,
                        periode_id,
                        source_id,
                        segment_id,
                        valeur,
                        statut,
                        date_extraction,
                        valide_depuis,
                        valide_jusqu_a,
                        est_courante
                    )
                    VALUES (
                        %s,
                        %s,
                        %s,
                        NULL,
                        %s,
                        'consolide',
                        NOW(),
                        NOW(),
                        NULL,
                        TRUE
                    )
                    """,
                    (
                        indicateur_cumul_id,
                        periode_id,
                        source_id,
                        float(row["cumul_annee"])
                    )
                )

                print(
                    f"✅ CIMENT_CUMUL inséré : "
                    f"{row['cumul_annee']} tonnes"
                )

            else:

                print(
                    "⏭️ CIMENT_CUMUL déjà présent."
                )

        # ----------------------------------------------------
        # Validation
        # ----------------------------------------------------

        conn.commit()

        print("\n✅ Chargement CIMENT terminé.")

    except Exception as e:

        conn.rollback()

        print(
            f"\n❌ Erreur pendant le chargement : {e}"
        )

        raise

    finally:

        cursor.close()
        conn.close()


# ============================================================
# Exécution
# ============================================================

if __name__ == "__main__":

    load_ciment()