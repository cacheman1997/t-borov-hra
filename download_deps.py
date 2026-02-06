import urllib.request
import os

files = {
    "lib/leaflet.css": "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css",
    "lib/leaflet.js": "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js",
    "lib/polylabel.js": "https://cdnjs.cloudflare.com/ajax/libs/polylabel/2.0.1/polylabel.js",
    "lib/socket.io.min.js": "https://cdn.socket.io/4.7.4/socket.io.min.js"
}

opener = urllib.request.build_opener()
opener.addheaders = [('User-Agent', 'Mozilla/5.0')]
urllib.request.install_opener(opener)

for path, url in files.items():
    try:
        print(f"Downloading {url} to {path}...")
        urllib.request.urlretrieve(url, path)
        print("Done.")
    except Exception as e:
        print(f"Failed to download {url}: {e}")
