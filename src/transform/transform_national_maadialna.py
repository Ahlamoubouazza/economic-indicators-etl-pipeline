import pandas as pd
from datetime import datetime

from src.extract.extract_national_maadialna import extract_national_statistics

def transform_national_maadialna():

    data = extract_national_statistics()


    row = {

        "ressources_totales_milliards_m3":
            data["ressources_totales"],

        "taux_remplissage_national":
            data["taux_remplissage_national"],

        "date_statistique":
            data["date_statistique"],

        "date_collecte":
            datetime.now().strftime("%Y-%m-%d")

    }


    df = pd.DataFrame([row])


    return df



if __name__ == "__main__":


    df = transform_national_maadialna()


    print(df)


    df.to_csv(
        "data/national_barrages.csv",
        index=False,
        encoding="utf-8-sig"
    )


    print("\n✅ fichier national_barrages.csv créé")