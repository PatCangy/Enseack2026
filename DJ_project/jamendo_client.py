import requests

clientId = "f5b09fc6"
baseUrl = "https://api.jamendo.com/v3.0/tracks/"

def getTracksByTag(tag, limit=10):
    params = {
        "client_id": clientId,
        "format": "json",
        "limit": limit,
        "tags": tag,
        "include": "musicinfo"
    }

    response = requests.get(baseUrl, params=params)
    response.raise_for_status()
    data = response.json()

    cleanedTracks = []

    for track in data.get("results", []):
        cleanedTracks.append({
            "id": track.get("id"),
            "name": track.get("name"),
            "artist": track.get("artist_name"),
            "audio": track.get("audio"),
            "duration": track.get("duration"),
            "musicinfo": track.get("musicinfo")
        })

    return cleanedTracks

tracks = getTracksByTag("electronic", 5)

for track in tracks:
    print(track)
