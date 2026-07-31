import requests
from bs4 import BeautifulSoup
import re


URL = "https://www.maadialna.ma/ar"



def extract_number(text):

    """
    Extraire un nombre depuis un texte arabe
    """

    result = re.search(r'\d+(\.\d+)?', text)

    if result:
        return float(result.group())

    return None



def extract_national_statistics():

    response = requests.get(URL)

    response.encoding = "utf-8"


    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )


    stats = {

        "ressources_totales": None,

        "taux_remplissage_national": None,

        "date_statistique": None

    }



    # bloc حالة السدود في المغرب

    bloc = soup.find(
        "div",
        class_="entete-etat-barrage"
    )


    if not bloc:
        return stats



    texte = bloc.get_text(
        " ",
        strip=True
    )


    print("DEBUG :")
    print(texte)



    # Ressources hydriques

    if "مليار متر مكعب" in texte:

        stats["ressources_totales"] = extract_number(
            texte
        )



    # Taux national

    taux = re.search(
        r'(\d+\.\d+)%'
        ,
        texte
    )


    if taux:

        stats["taux_remplissage_national"] = float(
            taux.group(1)
        )



    # Date

    date = re.search(
        r'يوم\s+(.*?)[\.،]',
        texte
    )


    if date:

        stats["date_statistique"] = date.group(1)



    return stats





if __name__ == "__main__":

    data = extract_national_statistics()

    print(data)