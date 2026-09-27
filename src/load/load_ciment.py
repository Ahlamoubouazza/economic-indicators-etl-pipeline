import os
import pandas as pd


def load_historical(new_file, historical_file):
    """
    Ajoute les nouvelles données à l'historique
    uniquement si elles n'existent pas déjà.
    """

    new_data = pd.read_csv(new_file, encoding="utf-8-sig")

    if os.path.exists(historical_file):

        old_data = pd.read_csv(
            historical_file,
            encoding="utf-8-sig"
        )

        historique = pd.concat(
            [old_data, new_data],
            ignore_index=True
        )

        historique = historique.drop_duplicates()

    else:

        historique = new_data

    historique.to_csv(
        historical_file,
        index=False,
        encoding="utf-8-sig"
    )

    print("Historique mis à jour.")

    return historique

if __name__ == "__main__":

    load_historical(
        "data/ciment.csv",
        "data/historique_ciment.csv"
    )