import os
import logging

import pandas as pd
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

from src.extract.extract_portwatch import extract_portwatch_data
from src.transform.transform_portwatch import transform_portwatch_data


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

TOLERANCE = 1e-6

# Nombre de valeurs envoyées à PostgreSQL par batch
BATCH_SIZE = 10000


# ============================================================
# CONNEXION POSTGRESQL
# ============================================================

def get_connection():

    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )


# ============================================================
# SOURCE
# ============================================================

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
            "PORTWATCH",
            "IMF PortWatch",
            "API",
            "Officielle"
        )
    )

    return cursor.fetchone()[0]


# ============================================================
# INDICATEURS PORTWATCH
# ============================================================

PORTWATCH_INDICATORS = {

    "portcalls": (
        "PORTCALLS",
        "Nombre total d escales portuaires",
        "Transport maritime",
        "Escales"
    ),

    "portcalls_container": (
        "PORTCALLS_CONTAINER",
        "Escales de navires porte-conteneurs",
        "Transport maritime",
        "Escales"
    ),

    "portcalls_dry_bulk": (
        "PORTCALLS_DRY_BULK",
        "Escales de navires vraquiers secs",
        "Transport maritime",
        "Escales"
    ),

    "portcalls_general_cargo": (
        "PORTCALLS_GENERAL_CARGO",
        "Escales de navires de cargaison generale",
        "Transport maritime",
        "Escales"
    ),

    "portcalls_roro": (
        "PORTCALLS_RORO",
        "Escales de navires Ro-Ro",
        "Transport maritime",
        "Escales"
    ),

    "portcalls_tanker": (
        "PORTCALLS_TANKER",
        "Escales de navires petroliers",
        "Transport maritime",
        "Escales"
    ),

    "portcalls_cargo": (
        "PORTCALLS_CARGO",
        "Escales de navires cargo",
        "Transport maritime",
        "Escales"
    ),

    "import": (
        "IMPORT",
        "Importations totales",
        "Commerce maritime",
        "Tonnes"
    ),

    "import_container": (
        "IMPORT_CONTAINER",
        "Importations par conteneurs",
        "Commerce maritime",
        "Tonnes"
    ),

    "import_dry_bulk": (
        "IMPORT_DRY_BULK",
        "Importations de vrac sec",
        "Commerce maritime",
        "Tonnes"
    ),

    "import_general_cargo": (
        "IMPORT_GENERAL_CARGO",
        "Importations de cargaison generale",
        "Commerce maritime",
        "Tonnes"
    ),

    "import_roro": (
        "IMPORT_RORO",
        "Importations Ro-Ro",
        "Commerce maritime",
        "Tonnes"
    ),

    "import_tanker": (
        "IMPORT_TANKER",
        "Importations par petroliers",
        "Commerce maritime",
        "Tonnes"
    ),

    "import_cargo": (
        "IMPORT_CARGO",
        "Importations de marchandises",
        "Commerce maritime",
        "Tonnes"
    ),

    "export": (
        "EXPORT",
        "Exportations totales",
        "Commerce maritime",
        "Tonnes"
    ),

    "export_container": (
        "EXPORT_CONTAINER",
        "Exportations par conteneurs",
        "Commerce maritime",
        "Tonnes"
    ),

    "export_dry_bulk": (
        "EXPORT_DRY_BULK",
        "Exportations de vrac sec",
        "Commerce maritime",
        "Tonnes"
    ),

    "export_general_cargo": (
        "EXPORT_GENERAL_CARGO",
        "Exportations de cargaison generale",
        "Commerce maritime",
        "Tonnes"
    ),

    "export_roro": (
        "EXPORT_RORO",
        "Exportations Ro-Ro",
        "Commerce maritime",
        "Tonnes"
    ),

    "export_tanker": (
        "EXPORT_TANKER",
        "Exportations par petroliers",
        "Commerce maritime",
        "Tonnes"
    ),

    "export_cargo": (
        "EXPORT_CARGO",
        "Exportations de marchandises",
        "Commerce maritime",
        "Tonnes"
    ),
}


# ============================================================
# RECUPERER / CREER UN INDICATEUR
# ============================================================

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


# ============================================================
# CHARGER LES 21 INDICATEURS
# ============================================================

def load_indicators(cursor):

    indicator_cache = {}

    for column, metadata in PORTWATCH_INDICATORS.items():

        code, nom, categorie, unite = metadata

        indicator_id = get_or_create_indicateur(
            cursor,
            code,
            nom,
            categorie,
            unite
        )

        indicator_cache[column] = indicator_id

    logger.info(
        "✅ %s indicateurs PortWatch préparés",
        len(indicator_cache)
    )

    return indicator_cache


# ============================================================
# RECUPERER / CREER UNE PERIODE
# ============================================================

def get_or_create_periode(
    cursor,
    date_reference,
    periode_cache
):

    date_reference = pd.to_datetime(
        date_reference
    ).date()

    if date_reference in periode_cache:

        return periode_cache[date_reference]

    trimestre = (
        (date_reference.month - 1) // 3
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
            date_reference,
            date_reference.year,
            date_reference.month,
            trimestre
        )
    )

    periode_id = cursor.fetchone()[0]

    periode_cache[date_reference] = periode_id

    return periode_id


# ============================================================
# RECUPERER / CREER UN PORT
# ============================================================

def get_or_create_port(
    cursor,
    portid,
    portname,
    port_cache
):

    key = str(portid)

    if key in port_cache:

        return port_cache[key]

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
            "PORT",
            key,
            str(portname)
        )
    )

    segment_id = cursor.fetchone()[0]

    port_cache[key] = segment_id

    return segment_id


# ============================================================
# CHARGER LES VALEURS COURANTES EN CACHE
# ============================================================

def load_current_values_cache(
    cursor,
    source_id
):

    logger.info(
        "📦 Chargement des valeurs courantes en cache..."
    )

    cursor.execute(
        """
        SELECT
            indicateur_id,
            periode_id,
            source_id,
            segment_id,
            id,
            valeur
        FROM fait_indicateur_valeur
        WHERE source_id = %s
          AND est_courante = TRUE;
        """,
        (source_id,)
    )

    cache = {}

    for row in cursor.fetchall():

        (
            indicateur_id,
            periode_id,
            source_id_db,
            segment_id,
            row_id,
            valeur
        ) = row

        key = (
            indicateur_id,
            periode_id,
            source_id_db,
            segment_id
        )

        cache[key] = {
            "id": row_id,
            "valeur": float(valeur)
        }

    logger.info(
        "📦 %s valeurs courantes chargées en cache",
        len(cache)
    )

    return cache


# ============================================================
# INSERTION BATCH
# ============================================================

def execute_insert_batch(
    cursor,
    records
):

    if not records:
        return

    query = """
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
        VALUES %s;
    """

    psycopg2.extras.execute_values(
        cursor,
        query,
        records,
        page_size=BATCH_SIZE
    )


# ============================================================
# CHARGEMENT PORTWATCH
# ============================================================

def load_portwatch():

    connection = None
    cursor = None

    stats = {
        "inserted": 0,
        "updated": 0,
        "unchanged": 0
    }

    try:

        # ====================================================
        # CONNEXION
        # ====================================================

        connection = get_connection()
        cursor = connection.cursor()

        logger.info(
            "✅ Connexion à PostgreSQL réussie"
        )

        # ====================================================
        # SOURCE
        # ====================================================

        source_id = get_or_create_source(cursor)

        logger.info(
            "Source PORTWATCH : id=%s",
            source_id
        )

        # ====================================================
        # INDICATEURS
        # ====================================================

        indicator_cache = load_indicators(cursor)

        # ====================================================
        # EXTRACTION
        # ====================================================

        logger.info(
            "🚢 Début extraction PortWatch..."
        )

        raw_data = extract_portwatch_data("MAR")

        logger.info(
            "Extraction terminée : %s lignes",
            len(raw_data)
        )

        # ====================================================
        # TRANSFORMATION
        # ====================================================

        df = transform_portwatch_data(raw_data)

        logger.info(
            "Transformation terminée : %s lignes",
            len(df)
        )

        # ====================================================
        # CACHES DIMENSIONS
        # ====================================================

        periode_cache = {}
        port_cache = {}

        # ----------------------------------------------------
        # PERIODES
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT
                id,
                date_reference
            FROM dim_periode;
            """
        )

        for row in cursor.fetchall():

            periode_cache[row[1]] = row[0]

        logger.info(
            "Périodes déjà présentes en cache : %s",
            len(periode_cache)
        )

        # ----------------------------------------------------
        # PORTS
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT
                id,
                code
            FROM dim_segment
            WHERE type_segment = 'PORT';
            """
        )

        for row in cursor.fetchall():

            port_cache[str(row[1])] = row[0]

        logger.info(
            "Ports déjà présents en cache : %s",
            len(port_cache)
        )

        # ====================================================
        # CACHE DES VALEURS COURANTES
        # ====================================================

        current_values_cache = load_current_values_cache(
            cursor,
            source_id
        )

        # ====================================================
        # PREPARATION DES LOTS
        # ====================================================

        insert_records = []

        update_ids = []

        total_rows = len(df)

        total_values = (
            total_rows
            * len(indicator_cache)
        )

        logger.info(
            "🚢 Début du traitement de %s observations",
            total_rows
        )

        logger.info(
            "📊 Nombre total de valeurs à traiter : %s",
            total_values
        )

        # ====================================================
        # PARCOURS DES OBSERVATIONS
        # ====================================================

        for index, row in df.iterrows():

            # ------------------------------------------------
            # PERIODE
            # ------------------------------------------------

            periode_id = get_or_create_periode(
                cursor,
                row["date"],
                periode_cache
            )

            # ------------------------------------------------
            # PORT
            # ------------------------------------------------

            segment_id = get_or_create_port(
                cursor,
                row["portid"],
                row["portname"],
                port_cache
            )

            # ------------------------------------------------
            # 21 INDICATEURS
            # ------------------------------------------------

            for column, indicator_id in indicator_cache.items():

                valeur = row[column]

                if pd.isna(valeur):

                    valeur = 0.0

                else:

                    valeur = float(valeur)

                key = (
                    indicator_id,
                    periode_id,
                    source_id,
                    segment_id
                )

                existing = current_values_cache.get(key)

                # ============================================
                # NOUVELLE VALEUR
                # ============================================

                if existing is None:

                    insert_records.append(
                        (
                            indicator_id,
                            periode_id,
                            source_id,
                            segment_id,
                            valeur,
                            "consolide",
                            True
                        )
                    )

                    stats["inserted"] += 1

                    current_values_cache[key] = {
                        "id": None,
                        "valeur": valeur
                    }

                # ============================================
                # VALEUR EXISTANTE
                # ============================================

                else:

                    old_value = existing["valeur"]

                    # ----------------------------------------
                    # IDENTIQUE
                    # ----------------------------------------

                    if abs(old_value - valeur) < TOLERANCE:

                        stats["unchanged"] += 1

                    # ----------------------------------------
                    # MODIFIEE
                    # ----------------------------------------

                    else:

                        update_ids.append(
                            existing["id"]
                        )

                        insert_records.append(
                            (
                                indicator_id,
                                periode_id,
                                source_id,
                                segment_id,
                                valeur,
                                "consolide",
                                True
                            )
                        )

                        stats["updated"] += 1

                        # Mise à jour du cache
                        current_values_cache[key] = {
                            "id": None,
                            "valeur": valeur
                        }

            # =================================================
            # EXECUTION BATCH
            # =================================================

            if len(insert_records) >= BATCH_SIZE:

                # ---------------------------------------------
                # Désactiver les anciennes valeurs modifiées
                # ---------------------------------------------

                if update_ids:

                    cursor.execute(
                        """
                        UPDATE fait_indicateur_valeur
                        SET
                            est_courante = FALSE,
                            valide_jusqu_a = NOW()
                        WHERE id = ANY(%s);
                        """,
                        (update_ids,)
                    )

                    update_ids.clear()

                # ---------------------------------------------
                # Insérer les nouvelles valeurs
                # ---------------------------------------------

                execute_insert_batch(
                    cursor,
                    insert_records
                )

                logger.info(
                    "📥 Batch INSERT exécuté : %s valeurs",
                    len(insert_records)
                )

                insert_records.clear()

            # =================================================
            # PROGRESSION
            # =================================================

            if (index + 1) % 1000 == 0:

                logger.info(
                    "Progression : %s / %s observations | "
                    "Insérées=%s | Modifiées=%s | Inchangées=%s",
                    index + 1,
                    total_rows,
                    stats["inserted"],
                    stats["updated"],
                    stats["unchanged"]
                )

        # ====================================================
        # DERNIER BATCH
        # ====================================================

        if update_ids:

            cursor.execute(
                """
                UPDATE fait_indicateur_valeur
                SET
                    est_courante = FALSE,
                    valide_jusqu_a = NOW()
                WHERE id = ANY(%s);
                """,
                (update_ids,)
            )

            update_ids.clear()

        if insert_records:

            execute_insert_batch(
                cursor,
                insert_records
            )

            logger.info(
                "📥 Dernier batch INSERT : %s valeurs",
                len(insert_records)
            )

            insert_records.clear()

        # ====================================================
        # COMMIT
        # ====================================================

        connection.commit()

        logger.info(
            "============================================"
        )

        logger.info(
            "✅ CHARGEMENT PORTWATCH TERMINÉ"
        )

        logger.info(
            "Nouvelles valeurs : %s",
            stats["inserted"]
        )

        logger.info(
            "Valeurs modifiées : %s",
            stats["updated"]
        )

        logger.info(
            "Valeurs inchangées : %s",
            stats["unchanged"]
        )

        logger.info(
            "Total traité : %s",
            (
                stats["inserted"]
                + stats["updated"]
                + stats["unchanged"]
            )
        )

        logger.info(
            "============================================"
        )

    except Exception:

        if connection:

            connection.rollback()

        logger.exception(
            "❌ Échec du chargement PortWatch"
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


# ============================================================
# EXECUTION
# ============================================================

if __name__ == "__main__":

    load_portwatch()