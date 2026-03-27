from jamendo_client import JamendoClient

client = JamendoClient()
tracks = client.search_tracks(["chillout"], limit=5)

for t in tracks:
    print(t["name"], "-", t["artist"], "| bpm:", t["bpm"])