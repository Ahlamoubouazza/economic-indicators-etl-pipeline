import re
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
from src.extract.extract_maadialna import extract_bassins
def extract_number(text):
    """
    Extraire un nombre depuis un texte arabe
    """
    result = re.search(r'\d+(\.\d+)?', text)
    if result:
        return float(result.group())
    return None
def parse_barrages(html):
    """
    Extraction des barrages depuis le HTML modal
    """
    soup = BeautifulSoup(
        html,
        "html.parser")
    barrages = []
    modal_body = soup.find(
        "div",
        class_="modal-body")
    if not modal_body:
        return barrages
    elements = modal_body.find_all(
        ["p", "ul"])
    barrage_name = None
    for element in elements:
        # Récupération du nom du barrage
        if element.name == "p":

            strong = element.find("strong")

            if strong:
                barrage_name = strong.get_text(
                    strip=True
                )


        # Récupération des informations
        elif element.name == "ul" and barrage_name:


            infos = {

                "nom_barrage": barrage_name,

                "taux_actuel": None,

                "taux_annee_precedente": None,

                "volume_barrage": None

            }


            for li in element.find_all("li"):


                text = li.get_text(
                    " ",
                    strip=True
                )


                # IMPORTANT :
                # Tester l'année précédente avant اليوم
                # car نفس اليوم contient اليوم

                if "الماضية" in text:

                    infos["taux_annee_precedente"] = extract_number(text)


                elif "اليوم" in text:

                    infos["taux_actuel"] = extract_number(text)


                elif "الحجم" in text:

                    infos["volume_barrage"] = extract_number(text)



            barrages.append(infos)

            barrage_name = None



    return barrages





def transform_maadialna():

    data = extract_bassins()

    rows = []


    for bassin in data:


        nom_bassin = bassin["title"]

        taux_bassin = bassin["field_taux_de_remplissage"]

        volume_bassin = bassin["field_volume"]


        html = bassin["field_modal_content_barrage"]


        barrages = parse_barrages(html)


        for barrage in barrages:


            rows.append({

                "bassin_hydraulique": nom_bassin,

                "taux_bassin": taux_bassin,

                "volume_bassin": volume_bassin,

                "nom_barrage": barrage["nom_barrage"],

                "taux_remplissage_actuel": barrage["taux_actuel"],

                "taux_annee_precedente": barrage["taux_annee_precedente"],

                "volume_barrage": barrage["volume_barrage"],

                "date_collecte": datetime.now().strftime("%Y-%m-%d")

            })


    return pd.DataFrame(rows)





if __name__ == "__main__":


    df = transform_maadialna()


    print(df)


    df.to_csv(

        "data/barrages.csv",

        index=False,

        encoding="utf-8-sig"

    )


    print("\n✅ fichier data/barrages.csv créé")