import logging
import pandas as pd

from src.extract.extract_portwatch import extract_portwatch_data


# ============================================================
# CONFIGURATION
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


# ============================================================
# COLONNES À CONSERVER
# ============================================================

COLUMNS_TO_KEEP = [
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


# ============================================================
# TRANSFORMATION
# ============================================================

def transform_portwatch_data(
    data: list[dict]
) -> pd.DataFrame:
    """
    Transforme les données brutes extraites depuis PortWatch
    en DataFrame propre et compatible avec PostgreSQL.
    """

    logging.info(
        "Début de la transformation de %s enregistrements",
        len(data)
    )

    # --------------------------------------------------------
    # Conversion en DataFrame
    # --------------------------------------------------------

    df = pd.DataFrame(data)

    logging.info(
        "DataFrame créé : %s lignes, %s colonnes",
        df.shape[0],
        df.shape[1]
    )

    # --------------------------------------------------------
    # Vérification des colonnes attendues
    # --------------------------------------------------------

    missing_columns = [
        col
        for col in COLUMNS_TO_KEEP
        if col not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Colonnes manquantes dans les données PortWatch : "
            f"{missing_columns}"
        )

    # --------------------------------------------------------
    # Conservation des colonnes utiles
    # --------------------------------------------------------

    df = df[COLUMNS_TO_KEEP].copy()

    # --------------------------------------------------------
    # Conversion de la date
    # --------------------------------------------------------

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce"
    )

    # Vérification des dates invalides
    invalid_dates = df["date"].isna().sum()

    if invalid_dates > 0:

        logging.warning(
            "%s dates invalides détectées",
            invalid_dates
        )

        df = df.dropna(
            subset=["date"]
        )

    # --------------------------------------------------------
    # Conversion des colonnes numériques
    # --------------------------------------------------------

    numeric_columns = [
        "year",
        "month",
        "day",

        "portcalls",
        "portcalls_container",
        "portcalls_dry_bulk",
        "portcalls_general_cargo",
        "portcalls_roro",
        "portcalls_tanker",
        "portcalls_cargo",

        "import",
        "import_container",
        "import_dry_bulk",
        "import_general_cargo",
        "import_roro",
        "import_tanker",
        "import_cargo",

        "export",
        "export_container",
        "export_dry_bulk",
        "export_general_cargo",
        "export_roro",
        "export_tanker",
        "export_cargo",
    ]

    for column in numeric_columns:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

        # Les valeurs manquantes sont remplacées par 0
        df[column] = (
            df[column]
            .fillna(0)
            .astype(int)
        )

    # --------------------------------------------------------
    # Suppression des doublons
    # --------------------------------------------------------

    duplicates_before = df.duplicated(
        subset=["portid", "date"]
    ).sum()

    if duplicates_before > 0:

        logging.warning(
            "%s doublons détectés sur "
            "(portid, date)",
            duplicates_before
        )

        df = df.drop_duplicates(
            subset=["portid", "date"],
            keep="last"
        )

    # --------------------------------------------------------
    # Tri chronologique
    # --------------------------------------------------------

    df = df.sort_values(
        by=["date", "portid"]
    ).reset_index(drop=True)

    # --------------------------------------------------------
    # RÉSULTAT
    # --------------------------------------------------------

    logging.info(
        "Transformation terminée : %s lignes, %s colonnes",
        df.shape[0],
        df.shape[1]
    )

    logging.info(
        "Période disponible : %s → %s",
        df["date"].min().date(),
        df["date"].max().date()
    )

    logging.info(
        "Nombre de ports : %s",
        df["portid"].nunique()
    )

    return df


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    # Extraction
    raw_data = extract_portwatch_data("MAR")

    # Transformation
    df = transform_portwatch_data(raw_data)

    print("\n=== TRANSFORMATION PORTWATCH VALIDÉE ===")

    print(
        f"\nNombre de lignes : {len(df)}"
    )

    print(
        f"Nombre de colonnes : {len(df.columns)}"
    )

    print(
        f"Nombre de ports : "
        f"{df['portid'].nunique()}"
    )

    print(
        f"Période : "
        f"{df['date'].min().date()} "
        f"→ "
        f"{df['date'].max().date()}"
    )

    print("\nColonnes :")

    for column in df.columns:
        print(f"- {column}")

    print("\nAperçu des données :")

    print(
        df.head(10).to_string(
            index=False
        )
    )