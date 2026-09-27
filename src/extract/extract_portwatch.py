import logging
import time
import requests
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
PORTWATCH_URL = (
    "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/"
    "ArcGIS/rest/services/Daily_Ports_Data/"
    "FeatureServer/0/query")
PAGE_SIZE = 500
CONNECT_TIMEOUT = 15
READ_TIMEOUT = 120
MAX_RETRIES = 5
RETRY_DELAY = 5
PAGE_DELAY = 1
OUT_FIELDS = [
    # Temporalité
    "date",
    "year",
    "month",
    "day",

    # Identification du port
    "portid",
    "portname",
    "country",
    "ISO3",

    # Activité maritime
    "portcalls",
    "portcalls_container",
    "portcalls_dry_bulk",
    "portcalls_general_cargo",
    "portcalls_roro",
    "portcalls_tanker",
    "portcalls_cargo",

    # Importations
    "import",
    "import_container",
    "import_dry_bulk",
    "import_general_cargo",
    "import_roro",
    "import_tanker",
    "import_cargo",

    # Exportations
    "export",
    "export_container",
    "export_dry_bulk",
    "export_general_cargo",
    "export_roro",
    "export_tanker",
    "export_cargo",
]


OUT_FIELDS_PARAM = ",".join(OUT_FIELDS)


# ============================================================
# SESSION HTTP
# ============================================================

def create_session() -> requests.Session:
    """
    Crée une session HTTP réutilisable.
    """

    session = requests.Session()

    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "ETL-Pipeline/1.0"
            )
        }
    )

    return session


# ============================================================
# EXTRACTION D'UNE PAGE
# ============================================================

def fetch_page(
    session: requests.Session,
    params: dict,
    page_number: int,
    offset: int,
) -> list[dict]:
    """
    Récupère une page ArcGIS avec plusieurs tentatives
    en cas de timeout ou d'erreur réseau.
    """

    for attempt in range(1, MAX_RETRIES + 1):

        try:

            logger.info(
                "Requête page %s (offset=%s) - tentative %s/%s",
                page_number,
                offset,
                attempt,
                MAX_RETRIES
            )

            response = session.get(
                PORTWATCH_URL,
                params=params,
                timeout=(
                    CONNECT_TIMEOUT,
                    READ_TIMEOUT
                )
            )

            response.raise_for_status()

            data = response.json()

            # ------------------------------------------------
            # Vérification d'une erreur ArcGIS
            # ------------------------------------------------

            if "error" in data:

                raise RuntimeError(
                    f"Erreur API PortWatch : {data['error']}"
                )

            features = data.get(
                "features",
                []
            )

            page_data = [
                feature["attributes"]
                for feature in features
                if "attributes" in feature
            ]

            return page_data

        # ----------------------------------------------------
        # Timeout
        # ----------------------------------------------------

        except requests.exceptions.Timeout as e:

            logger.warning(
                "⚠️ Timeout page %s (offset=%s), "
                "tentative %s/%s : %s",
                page_number,
                offset,
                attempt,
                MAX_RETRIES,
                e
            )

        # ----------------------------------------------------
        # Erreur de connexion
        # ----------------------------------------------------

        except requests.exceptions.ConnectionError as e:

            logger.warning(
                "⚠️ Erreur connexion page %s (offset=%s), "
                "tentative %s/%s : %s",
                page_number,
                offset,
                attempt,
                MAX_RETRIES,
                e
            )

        # ----------------------------------------------------
        # Erreur HTTP
        # ----------------------------------------------------

        except requests.exceptions.HTTPError as e:

            status_code = (
                e.response.status_code
                if e.response is not None
                else None
            )

            logger.warning(
                "⚠️ Erreur HTTP page %s (offset=%s), "
                "statut=%s, tentative %s/%s",
                page_number,
                offset,
                status_code,
                attempt,
                MAX_RETRIES
            )

            # Les erreurs 4xx ne sont généralement pas
            # récupérables avec un retry.
            if (
                status_code is not None
                and 400 <= status_code < 500
            ):
                raise

        # ----------------------------------------------------
        # Autres erreurs requests
        # ----------------------------------------------------

        except requests.exceptions.RequestException as e:

            logger.warning(
                "⚠️ Erreur requête page %s (offset=%s), "
                "tentative %s/%s : %s",
                page_number,
                offset,
                attempt,
                MAX_RETRIES,
                e
            )

        # ----------------------------------------------------
        # Erreur API ArcGIS
        # ----------------------------------------------------

        except RuntimeError:

            logger.exception(
                "❌ Erreur renvoyée par l'API ArcGIS "
                "pour la page %s (offset=%s)",
                page_number,
                offset
            )

            raise

        # ----------------------------------------------------
        # Nouvelle tentative
        # ----------------------------------------------------

        if attempt < MAX_RETRIES:

            delay = RETRY_DELAY * attempt

            logger.info(
                "⏳ Nouvelle tentative dans %s secondes...",
                delay
            )

            time.sleep(delay)

        else:

            logger.error(
                "❌ Échec définitif de la page %s "
                "(offset=%s) après %s tentatives",
                page_number,
                offset,
                MAX_RETRIES
            )

            raise RuntimeError(
                f"Impossible de récupérer la page {page_number} "
                f"(offset={offset}) après "
                f"{MAX_RETRIES} tentatives."
            )


# ============================================================
# EXTRACTION COMPLETE PORTWATCH
# ============================================================

def extract_portwatch_data(
    iso_code: str = "MAR"
) -> list[dict]:
    """
    Extrait toutes les données quotidiennes des ports
    depuis l'API PortWatch pour un pays donné.

    Gère :
    - pagination ArcGIS ;
    - timeout réseau ;
    - erreurs de connexion ;
    - erreurs HTTP temporaires ;
    - nouvelles tentatives automatiques ;
    - réduction du volume de données retourné.
    """

    logger.info(
        "🚢 Début de l'extraction PortWatch pour : %s",
        iso_code
    )

    session = create_session()

    all_ports_data = []

    offset = 0
    page_number = 1

    try:

        while True:

            logger.info(
                "Récupération de la page %s (offset=%s)",
                page_number,
                offset
            )

            params = {
                "where": f"ISO3 = '{iso_code}'",

                # IMPORTANT :
                # on ne demande que les colonnes utilisées
                # par transform_portwatch.py
                "outFields": OUT_FIELDS_PARAM,

                "returnGeometry": "false",

                "orderByFields": (
                    "date DESC, ObjectId DESC"
                ),

                "resultOffset": offset,
                "resultRecordCount": PAGE_SIZE,

                "f": "json"
            }

            # ------------------------------------------------
            # Récupération robuste
            # ------------------------------------------------

            page_data = fetch_page(
                session=session,
                params=params,
                page_number=page_number,
                offset=offset
            )

            # ------------------------------------------------
            # Ajout
            # ------------------------------------------------

            all_ports_data.extend(
                page_data
            )

            logger.info(
                "Page %s : %s enregistrements récupérés",
                page_number,
                len(page_data)
            )

            # ------------------------------------------------
            # Dernière page
            # ------------------------------------------------

            if len(page_data) < PAGE_SIZE:

                logger.info(
                    "Dernière page détectée."
                )

                break

            # ------------------------------------------------
            # Page suivante
            # ------------------------------------------------

            offset += PAGE_SIZE
            page_number += 1

            if PAGE_DELAY > 0:

                time.sleep(
                    PAGE_DELAY
                )

        logger.info(
            "✅ Extraction terminée : %s "
            "enregistrements récupérés au total",
            len(all_ports_data)
        )

        return all_ports_data

    finally:

        session.close()

        logger.info(
            "Session HTTP PortWatch fermée"
        )


# ============================================================
# TEST LOCAL
# ============================================================

if __name__ == "__main__":

    result = extract_portwatch_data("MAR")

    print(
        f"\nExtraction validée : "
        f"{len(result)} enregistrements récupérés au total."
    )

    if result:

        print("\nPremier enregistrement :")

        for key, value in result[0].items():

            print(
                f"{key}: {value}"
            )

        print("\nDernier enregistrement :")

        for key, value in result[-1].items():

            print(
                f"{key}: {value}"
            )