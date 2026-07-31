import requests


API_URL = "https://www.maadialna.ma/ar/get-bassin"


def extract_bassins():

    response = requests.get(
        API_URL,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    response.raise_for_status()

    return response.json()


if __name__ == "__main__":

    data = extract_bassins()

    print("Nombre de bassins :", len(data))

    print(data[0].keys())