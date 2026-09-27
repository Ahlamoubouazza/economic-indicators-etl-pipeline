import requests

url = "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/PortWatch_ports_database/FeatureServer/0/query"

params = {
    "where": "ISO3 = 'MAR'",
    "outFields": "*",
    "returnGeometry": "false",
    "f": "json"
}

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

response = requests.get(url, params=params, headers=headers)
data = response.json()

print(f"Statut HTTP : {response.status_code}")
print(f"Nombre de ports trouvés : {len(data.get('features', []))}")

if data.get("features"):
    print("\nExemple de données pour le premier port :")
    print(data["features"][0]["attributes"])