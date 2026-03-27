import requests

clientId = "f5b09fc6"
baseUrl = "https://api.jamendo.com/v3.0/tracks/"

params = {
    "client_id": clientId,
    "format": "json",
    "limit": 5,
    "tags": "electronic"
}

response = requests.get(baseUrl, params=params)
data = response.json()

print(data)