from src.extract.extract_maadialna import extract_bassins


data = extract_bassins()


for bassin in data:

    print("\n======================")
    print("BASSIN :", bassin["title"])


    html = bassin["field_modal_content_barrage"]


    # chercher les informations des barrages
    index = html.find("الحجم")


    if index != -1:

        print(html[index-1000:index+500])

    else:

        print("Mot الحجم non trouvé")


    break