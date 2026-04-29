import requests
import json
import re
from http.server import BaseHTTPRequestHandler

# --- CONFIGURATION ---
# Ton JSON qui contient les matchs (provenant d'ESPN / EPG Talk)
EPG_DATA_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

# Tes équipes à surveiller absolument
MY_TEAMS = ["CANADIENS", "MONTRÉAL", "BLUE JAYS", "RAPTORS", "CITY", "PSG", "F1", "MIAMI"]

# Ton dictionnaire de traduction (ID EPG -> Ton ID de Stream)
# C'est ici que la magie opère pour faire le lien
STREAM_MAP = {
    "I123.15676.schedulesdirect.org": "184813",  # RDS 1
    "I124.39080.schedulesdirect.org": "184814",  # RDS 2
    "I111.15670.schedulesdirect.org": "184816",  # TSN 1
    "I154.58314.schedulesdirect.org": "184821",  # TVA Sports
    "I1000.49609.schedulesdirect.org": "176800", # Sky Main Event
    "I446.52300.schedulesdirect.org": "157280",  # Sky Mexico
}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'audio/x-mpegurl; charset=utf-8')
        self.end_headers()

        # 1. Récupérer les événements sportifs (L'horaire ESPN/EPG)
        events = []
        try:
            r = requests.get(EPG_DATA_URL, timeout=5)
            # Nettoyage pour extraire le JSON pur
            match = re.search(r'\[.*\]', r.text, re.DOTALL)
            if match:
                events = json.loads(match.group(0))
        except:
            pass

        playlist = "#EXTM3U\n"
        added_streams = set()

        # 2. GÉNÉRATION DES POSTES CUSTOMS (Le matching)
        playlist += "\n# --- MATCHS EN DIRECT (CUSTOM) ---\n"
        
        for event in events:
            title = event.get('title', '')
            ch_id = event.get('ch', '')
            
            # Si l'événement contient une de tes équipes OU est un "Live" important
            is_priority = any(team in title.upper() for team in MY_TEAMS) or "LIVE" in title.upper()
            
            # Si on a cet ID de chaîne dans notre dictionnaire de streams
            if is_priority and ch_id in STREAM_MAP:
                stream_id = STREAM_MAP[ch_id]
                playlist += f'#EXTINF:-1, ⭐ {title}\n'
                playlist += f'{STREAM_BASE}/{stream_id}\n'
                added_streams.add(ch_id)

        # 3. SECTION DE SECOURS (Tes chaînes habituelles si rien ne match)
        playlist += "\n# --- TES CHAÎNES FIXES ---\n"
        for ch_id, stream_id in STREAM_MAP.items():
            if ch_id not in added_streams:
                # On essaie de mettre le nom de ce qui joue, sinon juste le nom de la chaîne
                current_prog = next((e['title'] for e in events if e['ch'] == ch_id), "Sport")
                playlist += f'#EXTINF:-1, [{ch_id.split(".")[0]}] {current_prog}\n'
                playlist += f'{STREAM_BASE}/{stream_id}\n'

        self.wfile.write(playlist.encode('utf-8'))
        
