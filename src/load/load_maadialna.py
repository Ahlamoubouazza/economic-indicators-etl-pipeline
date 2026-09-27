import pandas as pd
import os
import logging


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


def load_historical(new_file, historical_file):
    """
    Ajoute une nouvelle collecte uniquement si les données ont changé.
    Retourne :
        True  -> changement détecté
        False -> aucune modification
    """

    # Lecture des nouvelles données
    new_data = pd.read_csv(
        new_file,
        encoding="utf-8-sig"
    )


    # Premier lancement : création de l'historique
    if not os.path.exists(historical_file):

        new_data.to_csv(
            historical_file,
            index=False,
            encoding="utf-8-sig"
        )

        logger.info(
            "➕ Premier historique créé : %s lignes ajoutées",
            len(new_data)
        )

        return True


    # Lecture de l'historique existant
    old_data = pd.read_csv(
        historical_file,
        encoding="utf-8-sig"
    )


    # Vérification de la présence de date_collecte
    if "date_collecte" in old_data.columns:

        # Dernière collecte enregistrée
        last_date = old_data["date_collecte"].max()

        # Dernier état du site
        last_data = old_data[
            old_data["date_collecte"] == last_date
        ].copy()

    else:

        last_data = old_data.copy()


    # Colonnes utilisées pour comparer
    # (on ignore date_collecte car elle change à chaque exécution)
    columns_to_compare = [
        col for col in new_data.columns
        if col != "date_collecte"
    ]


    # Tri pour comparer les DataFrames correctement
    new_compare = (
        new_data[columns_to_compare]
        .sort_values(by=columns_to_compare)
        .reset_index(drop=True)
    )


    last_compare = (
        last_data[columns_to_compare]
        .sort_values(by=columns_to_compare)
        .reset_index(drop=True)
    )


    # Aucun changement détecté
    if new_compare.equals(last_compare):

        logger.info(
            "⏭️ Aucun changement détecté : historique non modifié"
        )

        return False


    # Changement détecté : ajout dans l'historique
    updated_data = pd.concat(
        [old_data, new_data],
        ignore_index=True
    )


    # Suppression des doublons exacts
    updated_data = updated_data.drop_duplicates()


    updated_data.to_csv(
        historical_file,
        index=False,
        encoding="utf-8-sig"
    )


    logger.info(
        "🔄 Changement détecté : %s nouvelles lignes ajoutées",
        len(new_data)
    )


    return True



if __name__ == "__main__":


    # Historique des barrages
    changed_barrages = load_historical(
        "data/barrages.csv",
        "data/historique_barrages.csv"
    )


    # Historique des statistiques nationales
    changed_national = load_historical(
        "data/national_barrages.csv",
        "data/history_national_barrages.csv"
    )


    if changed_barrages or changed_national:

        print(
            "✅ Au moins une source a changé"
        )

    else:

        print(
            "⏭️ Aucun changement détecté"
        )