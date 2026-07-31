import os
import logging
import pandas as pd
import psycopg2
from dotenv import load_dotenv

# ============================================
# LOGGING
# ============================================
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ============================================
# CHARGER LES VARIABLES DU FICHIER .env
# ============================================
load_dotenv()

# Tolérance pour la comparaison de valeurs numériques (évite les faux positifs d'arrondi)
TOLERANCE = 1e-6


# ============================================
# CONNEXION POSTGRESQL
# ============================================
def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )


# ============================================
# RECUPERER OU CREER UNE SOURCE
# ============================================
def get_or_create_source(cursor):
    cursor.execute(
        """
        INSERT INTO dim_source (code, nom, type_source, niveau_fiabilite)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (code) DO UPDATE SET
            nom = EXCLUDED.nom,
            type_source = EXCLUDED.type_source,
            niveau_fiabilite = EXCLUDED.niveau_fiabilite
        RETURNING id;
        """,
        ("MAADIALNA", "Maadialna", "Web scraping", "Officielle"),
    )
    return cursor.fetchone()[0]


# ============================================
# RECUPERER OU CREER UN INDICATEUR
# ============================================
def get_or_create_indicateur(cursor, code, nom, categorie, unite):
    cursor.execute(
        """
        INSERT INTO dim_indicateur (code, nom, categorie, unite)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (code) DO UPDATE SET
            nom = EXCLUDED.nom,
            categorie = EXCLUDED.categorie,
            unite = EXCLUDED.unite
        RETURNING id;
        """,
        (code, nom, categorie, unite),
    )
    return cursor.fetchone()[0]


# ============================================
# RECUPERER OU CREER UNE PERIODE
# ============================================
def get_or_create_periode(cursor, date_collecte):
    date_collecte = pd.to_datetime(date_collecte).date()
    trimestre = ((date_collecte.month - 1) // 3) + 1

    cursor.execute(
        """
        INSERT INTO dim_periode (date_reference, annee, mois, trimestre)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (date_reference) DO UPDATE SET
            annee = EXCLUDED.annee,
            mois = EXCLUDED.mois,
            trimestre = EXCLUDED.trimestre
        RETURNING id;
        """,
        (date_collecte, date_collecte.year, date_collecte.month, trimestre),
    )
    return cursor.fetchone()[0]


# ============================================
# RECUPERER OU CREER UN SEGMENT
# ============================================
def get_or_create_segment(cursor, type_segment, code, libelle):
    cursor.execute(
        """
        INSERT INTO dim_segment (type_segment, code, libelle)
        VALUES (%s, %s, %s)
        ON CONFLICT (type_segment, code) DO UPDATE SET
            libelle = EXCLUDED.libelle
        RETURNING id;
        """,
        (type_segment, code, libelle),
    )
    return cursor.fetchone()[0]


# ============================================
# INSERER OU METTRE A JOUR UNE VALEUR (historisation SCD Type 2)
# ============================================
def insert_value(cursor, indicateur_id, periode_id, source_id, segment_id, valeur, statut="consolide"):
    """
    statut : 'provisoire' / 'revise' / 'consolide'.
    Par défaut 'consolide' pour Maadialna (pas de logique de révision pour cette source),
    mais reste un paramètre explicite pour être réutilisable avec l'Excel OC (Étape 15),
    où le statut réel devra être calculé, jamais codé en dur.
    """
    cursor.execute(
        """
        SELECT id, valeur
        FROM fait_indicateur_valeur
        WHERE indicateur_id = %s AND periode_id = %s
          AND source_id = %s AND segment_id = %s
          AND est_courante = TRUE;
        """,
        (indicateur_id, periode_id, source_id, segment_id),
    )
    valeur_existante = cursor.fetchone()

    if valeur_existante is None:
        cursor.execute(
            """
            INSERT INTO fait_indicateur_valeur
                (indicateur_id, periode_id, source_id, segment_id, valeur, statut, est_courante)
            VALUES (%s, %s, %s, %s, %s, %s, TRUE);
            """,
            (indicateur_id, periode_id, source_id, segment_id, float(valeur), statut),
        )
        logger.info("➕ Nouvelle valeur ajoutée : %s", valeur)
        return

    id_existant, ancienne_valeur = valeur_existante

    if abs(float(ancienne_valeur) - float(valeur)) < TOLERANCE:
        logger.info("⏭️ Valeur déjà enregistrée : %s", valeur)
        return

    # Fermer l'ancienne version (jamais d'UPDATE sur la colonne "valeur")
    cursor.execute(
        """
        UPDATE fait_indicateur_valeur
        SET est_courante = FALSE, valide_jusqu_a = NOW()
        WHERE id = %s;
        """,
        (id_existant,),
    )
    # Insérer la nouvelle version
    cursor.execute(
        """
        INSERT INTO fait_indicateur_valeur
            (indicateur_id, periode_id, source_id, segment_id, valeur, statut, est_courante, valide_depuis)
        VALUES (%s, %s, %s, %s, %s, %s, TRUE, NOW());
        """,
        (indicateur_id, periode_id, source_id, segment_id, float(valeur), statut),
    )
    logger.info("🔄 Mise à jour détectée : %s → %s", ancienne_valeur, valeur)


# ============================================
# CHARGEMENT PRINCIPAL
# ============================================
def load_maadialna(csv_path="data/historique_barrages.csv"):
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Fichier introuvable : {csv_path}")

    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    logger.info("Fichier lu : %s lignes, colonnes : %s", len(df), df.columns.tolist())

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()
        logger.info("✅ Connexion à PostgreSQL réussie")

        source_id = get_or_create_source(cursor)

        indicateur_taux_bassin_id = get_or_create_indicateur(
            cursor, "TAUX_BASSIN", "Taux de remplissage du bassin", "eau", "%"
        )
        indicateur_taux_barrage_id = get_or_create_indicateur(
            cursor, "TAUX_BARRAGE", "Taux de remplissage du barrage", "eau", "%"
        )
        indicateur_volume_id = get_or_create_indicateur(
            cursor, "VOLUME_BARRAGE", "Volume disponible du barrage", "eau", "millions_m3"
        )

        for _, row in df.iterrows():
            periode_id = get_or_create_periode(cursor, row["date_collecte"])

            bassin_id = get_or_create_segment(
                cursor, "BASSIN", str(row["bassin_hydraulique"]), str(row["bassin_hydraulique"])
            )
            barrage_id = get_or_create_segment(
                cursor, "BARRAGE", str(row["nom_barrage"]), str(row["nom_barrage"])
            )

            insert_value(cursor, indicateur_taux_bassin_id, periode_id, source_id, bassin_id, row["taux_bassin"])
            insert_value(cursor, indicateur_taux_barrage_id, periode_id, source_id, barrage_id, row["taux_remplissage_actuel"])
            insert_value(cursor, indicateur_volume_id, periode_id, source_id, barrage_id, row["volume_barrage"])

        connection.commit()
        logger.info("✅ Chargement terminé : %s lignes traitées", len(df))

    except Exception:
        if connection:
            connection.rollback()
        logger.exception("❌ Échec du chargement Maadialna")
        raise  # <-- on relance l'erreur : indispensable pour Airflow plus tard

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
            logger.info("Connexion PostgreSQL fermée")


# ============================================
# EXECUTION
# ============================================
if __name__ == "__main__":
    load_maadialna()