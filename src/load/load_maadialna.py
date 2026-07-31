import pandas as pd
import os


def load_historical(new_file, historical_file):

    new_data = pd.read_csv(
        new_file,
        encoding="utf-8-sig"
    )

    if os.path.exists(historical_file):

        old_data = pd.read_csv(
            historical_file,
            encoding="utf-8-sig"
        )

        df = pd.concat(
            [old_data, new_data],
            ignore_index=True
        )

    else:

        df = new_data

    df = df.drop_duplicates()

    df.to_csv(
        historical_file,
        index=False,
        encoding="utf-8-sig"
    )


if __name__ == "__main__":

    # Historique des barrages
    load_historical(
        "data/barrages.csv",
        "data/historique_barrages.csv"
    )

    # Historique des statistiques nationales
    load_historical(
        "data/national_barrages.csv",
        "data/history_national_barrages.csv"
    )

    print("✅ Les historiques ont été mis à jour")