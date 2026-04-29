from http.server import BaseHTTPRequestHandler
import requests
import json
import re
from datetime import datetime, timedelta

# --- CONFIGURATION ---
JSON_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

# TABLE D'ÉQUIVALENCE (L'ID du guide ESPN -> Ton ID de Stream)
MAP = {
    "I123.15676.schedulesdirect.org": "184813", # RDS 1
    "I124.39080.schedulesdirect.org": "184814", # RDS 2
    "I111.15670.schedulesdirect.org": "184816", # TSN 1
    "I154.58314.schedulesdirect.org": "184821", # TVA Sports
    "I428.49882.gracenote.com": "71518",        # Sportsnet East
    "I432.49886.gracenote.com": "71522",        # Sportsnet One
    "I155.58434.schedulesdirect.org": "184817", # Sportsnet West (Exemple)
    "I1000.49609.schedulesdirect.org": "176800",# Sky Main Event
    "I1001.104327.schedulesdirect.org": "176801" # Sky Football
}

PRIORITIES = ["CANADIENS", "MONTRÉAL", "PSG", "CITY", "F1", "EFL", "LIVE"]

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 1. Aller chercher la vérité sur GitHub (Le JSON d'ESPN)
        try:
            r = requests.get(JSON_URL, timeout=5)
            events = json.loads(re.search(r'\[.*\]', r.text, re.DOTALL).group(0))
        except:
            events = []

        # 2. Matcher les événements ESPN avec nos Streams
        matches = []
        for e in events:
            ch_id = e.get('ch')
            if ch_id in MAP:
                title = e.get('title', '').upper()
                score = next((i for i, t in enumerate(PRIORITIES) if t in title), 99)
                matches.append({'title': e['title'], 'sid': MAP[ch_id], 'start': e['start'], 'score': score})
        
        matches.sort(key=lambda x: x['score'])

        # --- SORTIE XMLTV (Le Guide pour l'Apple TV) ---
        if "type=xml" in self.path:
            self.send_response(200)
            self.send_header('Content-type', 'application/xml; charset=utf-8')
            self.end_headers()
            
            xml = '<?xml version="1.0" encoding="UTF-8"?><tv>'
            for i in range(1, 6):
                xml += f'<channel id="CHOIX.{i}"><display-name>CHOIX {i}</display-name></channel>'
                if (i-1) < len(matches):
                    m = matches[i-1]
                    # On nettoie la date pour le format XMLTV (YYYYMMDDHHMMSS +0000)
                    t = m['start'].replace(" ", "").replace("+0000", "")
                    start = f"{t} +0000"
                    # Fin fictive (+3h) pour la barre de progression
                    stop = (datetime.strptime(t[:12], "%Y%m%d%H%M") + timedelta(hours=3)).strftime("%Y%m%d%H%M%S") + " +0000"
                    
                    xml += f'<programme start="{start}" stop="{stop}" channel="CHOIX.{i}">'
                    xml += f'<title lang="fr">{m["title"]}</title></programme>'
            xml += '</tv>'
            self.wfile.write(xml.encode('utf-8'))

        # --- SORTIE M3U (La Playlist) ---
        else:
            self.send_response(200)
            self.send_header('Content-type', 'audio/x-mpegurl')
            self.end_headers()
            
            host = self.headers.get('Host')
            playlist = f'#EXTM3U x-tvg-url="https://{host}/api?type=xml"\n'
            
            for i in range(1, 6):
                if (i-1) < len(matches):
                    m = matches[i-1]
                    playlist += f'#EXTINF:-1 tvg-id="CHOIX.{i}", CHOIX {i} : {m["title"]}\n'
                    playlist += f'{STREAM_BASE}/{m["sid"]}\n'
                else:
                    playlist += f'#EXTINF:-1 tvg-id="CHOIX.{i}", CHOIX {i} (A venir)\n'
                    playlist += f'http://0.0.0.0\n'
            
            self.wfile.write(playlist.encode('utf-8'))
            
