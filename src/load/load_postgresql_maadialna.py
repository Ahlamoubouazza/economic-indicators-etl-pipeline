import os
import logging
import pandas as pd
import psycopg2
from dotenv import load_dotenv


# ============================================
# LOGGING
# ============================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


# ============================================
# CHARGER LES VARIABLES DU FICHIER .env
# ============================================

load_dotenv()


# Tolérance pour la comparaison des valeurs numériques

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

        password=os.getenv("DB_PASSWORD")

    )


# ============================================
# RECUPERER OU CREER UNE SOURCE
# ============================================

def get_or_create_source(cursor):

    cursor.execute(

        """

        INSERT INTO dim_source
        (
            code,
            nom,
            type_source,
            niveau_fiabilite
        )

        VALUES
        (
            %s,
            %s,
            %s,
            %s
        )

        ON CONFLICT (code)

        DO UPDATE SET

            nom = EXCLUDED.nom,

            type_source = EXCLUDED.type_source,

            niveau_fiabilite = EXCLUDED.niveau_fiabilite

        RETURNING id;

        """,

        (
            "MAADIALNA",
            "Maadialna",
            "Web scraping",
            "Officielle"
        )

    )

    return cursor.fetchone()[0]


# ============================================
# RECUPERER OU CREER UN INDICATEUR
# ============================================

def get_or_create_indicateur(

    cursor,

    code,

    nom,

    categorie,

    unite

):

    cursor.execute(

        """

        INSERT INTO dim_indicateur
        (
            code,
            nom,
            categorie,
            unite
        )

        VALUES
        (
            %s,
            %s,
            %s,
            %s
        )

        ON CONFLICT (code)

        DO UPDATE SET

            nom = EXCLUDED.nom,

            categorie = EXCLUDED.categorie,

            unite = EXCLUDED.unite

        RETURNING id;

        """,

        (
            code,
            nom,
            categorie,
            unite
        )

    )

    return cursor.fetchone()[0]


# ============================================
# RECUPERER OU CREER UNE PERIODE
# ============================================

def get_or_create_periode(

    cursor,

    date_collecte

):

    date_collecte = (

        pd.to_datetime(
            date_collecte
        ).date()

    )


    trimestre = (

        (
            date_collecte.month - 1
        ) // 3

    ) + 1


    cursor.execute(

        """

        INSERT INTO dim_periode
        (
            date_reference,
            annee,
            mois,
            trimestre
        )

        VALUES
        (
            %s,
            %s,
            %s,
            %s
        )

        ON CONFLICT (date_reference)

        DO UPDATE SET

            annee = EXCLUDED.annee,

            mois = EXCLUDED.mois,

            trimestre = EXCLUDED.trimestre

        RETURNING id;

        """,

        (
            date_collecte,

            date_collecte.year,

            date_collecte.month,

            trimestre
        )

    )

    return cursor.fetchone()[0]


# ============================================
# RECUPERER OU CREER UN SEGMENT
# ============================================

def get_or_create_segment(

    cursor,

    type_segment,

    code,

    libelle

):

    cursor.execute(

        """

        INSERT INTO dim_segment
        (
            type_segment,
            code,
            libelle
        )

        VALUES
        (
            %s,
            %s,
            %s
        )

        ON CONFLICT
        (
            type_segment,
            code
        )

        DO UPDATE SET

            libelle = EXCLUDED.libelle

        RETURNING id;

        """,

        (
            type_segment,
            code,
            libelle
        )

    )

    return cursor.fetchone()[0]


# ============================================
# INSERER OU METTRE A JOUR UNE VALEUR
# HISTORISATION SCD TYPE 2
# ============================================

def insert_value(

    cursor,

    indicateur_id,

    periode_id,

    source_id,

    segment_id,

    valeur,

    statut="consolide"

):

    # Rechercher une valeur courante

    cursor.execute(

        """

        SELECT
            id,
            valeur

        FROM fait_indicateur_valeur

        WHERE indicateur_id = %s

          AND periode_id = %s

          AND source_id = %s

          AND segment_id = %s

          AND est_courante = TRUE;

        """,

        (

            indicateur_id,

            periode_id,

            source_id,

            segment_id

        )

    )


    valeur_existante = (

        cursor.fetchone()

    )


    # ----------------------------------------
    # CAS 1 :
    # Aucune valeur courante
    # ----------------------------------------

    if valeur_existante is None:

        cursor.execute(

            """

            INSERT INTO fait_indicateur_valeur

            (
                indicateur_id,
                periode_id,
                source_id,
                segment_id,
                valeur,
                statut,
                est_courante
            )

            VALUES

            (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                TRUE
            );

            """,

            (

                indicateur_id,

                periode_id,

                source_id,

                segment_id,

                float(valeur),

                statut

            )

        )


        logger.info(

            "➕ Nouvelle valeur ajoutée : %s",

            valeur

        )


        return


    # ----------------------------------------
    # CAS 2 :
    # Une valeur existe déjà
    # ----------------------------------------

    id_existant, ancienne_valeur = (

        valeur_existante

    )


    # ----------------------------------------
    # CAS 2A :
    # La valeur est identique
    # ----------------------------------------

    if (

        abs(

            float(ancienne_valeur)

            -

            float(valeur)

        )

        <

        TOLERANCE

    ):

        logger.info(

            "⏭️ Valeur déjà enregistrée : %s",

            valeur

        )


        return


    # ----------------------------------------
    # CAS 2B :
    # La valeur a changé
    # ----------------------------------------

    cursor.execute(

        """

        UPDATE fait_indicateur_valeur

        SET

            est_courante = FALSE,

            valide_jusqu_a = NOW()

        WHERE id = %s;

        """,

        (

            id_existant,

        )

    )


    cursor.execute(

        """

        INSERT INTO fait_indicateur_valeur

        (
            indicateur_id,
            periode_id,
            source_id,
            segment_id,
            valeur,
            statut,
            est_courante,
            valide_depuis
        )

        VALUES

        (
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            TRUE,
            NOW()
        );

        """,

        (

            indicateur_id,

            periode_id,

            source_id,

            segment_id,

            float(valeur),

            statut

        )

    )


    logger.info(

        "🔄 Mise à jour détectée : %s → %s",

        ancienne_valeur,

        valeur

    )


# ============================================
# CHARGER LES DONNEES DETAILLEES
# BASSINS ET BARRAGES
# ============================================

def load_barrages(

    cursor,

    source_id,

    csv_path

):

    if not os.path.exists(

        csv_path

    ):

        raise FileNotFoundError(

            f"Fichier introuvable : {csv_path}"

        )


    df = pd.read_csv(

        csv_path,

        encoding="utf-8-sig"

    )


    logger.info(

        "Fichier barrages lu : %s lignes",

        len(df)

    )


    # ----------------------------------------
    # CREER LES INDICATEURS
    # ----------------------------------------

    indicateur_taux_bassin_id = (

        get_or_create_indicateur(

            cursor,

            "TAUX_BASSIN",

            "Taux de remplissage du bassin",

            "Ressources hydriques",

            "%"

        )

    )


    indicateur_taux_barrage_id = (

        get_or_create_indicateur(

            cursor,

            "TAUX_BARRAGE",

            "Taux de remplissage du barrage",

            "Ressources hydriques",

            "%"

        )

    )


    indicateur_volume_id = (

        get_or_create_indicateur(

            cursor,

            "VOLUME_BARRAGE",

            "Volume disponible du barrage",

            "Ressources hydriques",

            "Millions de m3"

        )

    )


    # ----------------------------------------
    # PARCOURIR LES LIGNES
    # ----------------------------------------

    for _, row in df.iterrows():


        periode_id = (

            get_or_create_periode(

                cursor,

                row["date_collecte"]

            )

        )


        bassin = str(

            row[
                "bassin_hydraulique"
            ]

        )


        bassin_id = (

            get_or_create_segment(

                cursor,

                "BASSIN",

                bassin,

                bassin

            )

        )


        barrage = str(

            row[
                "nom_barrage"
            ]

        )


        barrage_id = (

            get_or_create_segment(

                cursor,

                "BARRAGE",

                barrage,

                barrage

            )

        )


        # Taux du bassin

        insert_value(

            cursor,

            indicateur_taux_bassin_id,

            periode_id,

            source_id,

            bassin_id,

            row[
                "taux_bassin"
            ]

        )


        # Taux du barrage

        insert_value(

            cursor,

            indicateur_taux_barrage_id,

            periode_id,

            source_id,

            barrage_id,

            row[
                "taux_remplissage_actuel"
            ]

        )


        # Volume du barrage

        insert_value(

            cursor,

            indicateur_volume_id,

            periode_id,

            source_id,

            barrage_id,

            row[
                "volume_barrage"
            ]

        )


    logger.info(

        "✅ Données détaillées chargées : %s lignes",

        len(df)

    )


# ============================================
# CHARGER LES DONNEES NATIONALES
# ============================================

def load_national_barrages(

    cursor,

    source_id,

    csv_path

):

    if not os.path.exists(

        csv_path

    ):

        raise FileNotFoundError(

            f"Fichier introuvable : {csv_path}"

        )


    df = pd.read_csv(

        csv_path,

        encoding="utf-8-sig"

    )


    logger.info(

        "Fichier national lu : %s lignes",

        len(df)

    )


    # ----------------------------------------
    # CREER LES INDICATEURS NATIONAUX
    # ----------------------------------------

    indicateur_ressources_id = (

        get_or_create_indicateur(

            cursor,

            "RESSOURCES_NATIONALES",

            "Ressources hydriques totales nationales",

            "Ressources hydriques",

            "Milliards de m3"

        )

    )


    indicateur_taux_national_id = (

        get_or_create_indicateur(

            cursor,

            "TAUX_REMPLISSAGE_NATIONAL",

            "Taux national de remplissage des barrages",

            "Ressources hydriques",

            "%"

        )

    )


    # ----------------------------------------
    # CREER LE SEGMENT NATIONAL
    # ----------------------------------------

    national_id = (

        get_or_create_segment(

            cursor,

            "NATIONAL",

            "MAROC",

            "Maroc"

        )

    )


    # ----------------------------------------
    # PARCOURIR LES LIGNES
    # ----------------------------------------

    for _, row in df.iterrows():


        periode_id = (

            get_or_create_periode(

                cursor,

                row[
                    "date_collecte"
                ]

            )

        )


        # Ressources nationales

        insert_value(

            cursor,

            indicateur_ressources_id,

            periode_id,

            source_id,

            national_id,

            row[
                "ressources_totales_milliards_m3"
            ]

        )


        # Taux national

        insert_value(

            cursor,

            indicateur_taux_national_id,

            periode_id,

            source_id,

            national_id,

            row[
                "taux_remplissage_national"
            ]

        )


    logger.info(

        "✅ Données nationales chargées : %s lignes",

        len(df)

    )


# ============================================
# CHARGEMENT PRINCIPAL
# ============================================

def load_maadialna(

    barrages_path="data/historique_barrages.csv",

    national_path="data/history_national_barrages.csv"

):

    connection = None

    cursor = None


    try:


        # ------------------------------------
        # CONNEXION
        # ------------------------------------

        connection = (

            get_connection()

        )


        cursor = (

            connection.cursor()

        )


        logger.info(

            "✅ Connexion à PostgreSQL réussie"

        )


        # ------------------------------------
        # SOURCE MAADIALNA
        # ------------------------------------

        source_id = (

            get_or_create_source(

                cursor

            )

        )


        # ------------------------------------
        # CHARGEMENT DES BARRAGES
        # ------------------------------------

        load_barrages(

            cursor,

            source_id,

            barrages_path

        )


        # ------------------------------------
        # CHARGEMENT DES DONNEES NATIONALES
        # ------------------------------------

        load_national_barrages(

            cursor,

            source_id,

            national_path

        )


        # ------------------------------------
        # SAUVEGARDER
        # ------------------------------------

        connection.commit()


        logger.info(

            "✅ Chargement Maadialna terminé"

        )


    except Exception:


        if connection:

            connection.rollback()


        logger.exception(

            "❌ Échec du chargement Maadialna"

        )


        raise


    finally:


        if cursor:

            cursor.close()


        if connection:

            connection.close()


            logger.info(

                "Connexion PostgreSQL fermée"

            )


# ============================================
# EXECUTION
# ============================================

if __name__ == "__main__":

    load_maadialna()