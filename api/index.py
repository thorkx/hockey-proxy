from http.server import BaseHTTPRequestHandler
import requests
import json
import re
from datetime import datetime, timedelta

# --- CONFIGURATION ---
JSON_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

# ÉQUIVALENCE STRICTE (Basée sur tes IDs filtered_epg)
MAP = {
    "I123.15676.schedulesdirect.org": "184813", # RDS 1
    "I124.39080.schedulesdirect.org": "184814", # RDS 2
    "I111.15670.schedulesdirect.org": "184816", # TSN 1
    "I154.58314.schedulesdirect.org": "184821", # TVA Sports
    "I1000.49609.schedulesdirect.org": "176800",# Sky Main Event
    "I1001.104327.schedulesdirect.org": "176801",# Sky Football
    "I446.52300.schedulesdirect.org": "157280",  # Sky Mexico (Sportsnet/LaLiga)
    "I428.49882.gracenote.com": "71518",        # Sportsnet East
    "I432.49886.gracenote.com": "71522",        # Sportsnet One
}

PRIORITIES = ["CANADIENS", "MONTRÉAL", "PSG", "CITY", "F1", "EFL", "LIVE"]

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 1. Extraction propre du JSON
        try:
            r = requests.get(JSON_URL, timeout=5)
            content = re.search(r'\[.*\]', r.text, re.DOTALL).group(0)
            events = json.loads(content)
        except:
            events = []

        # 2. Matching des événements avec les flux
        matches = []
        for e in events:
            ch_id = e.get('ch', '').strip()
            if ch_id in MAP:
                title = e.get('title', 'Sport').upper()
                score = next((i for i, t in enumerate(PRIORITIES) if t in title), 99)
                matches.append({
                    'title': e.get('title'),
                    'sid': MAP[ch_id],
                    'start': e.get('start', '').replace(" ", "").replace("+0000", ""),
                    'score': score
                })
        
        matches.sort(key=lambda x: x['score'])

        # --- SORTIE XMLTV (Le Guide) ---
        if "type=xml" in self.path:
            self.send_response(200)
            self.send_header('Content-type', 'application/xml; charset=utf-8')
            self.end_headers()
            
            xml = '<?xml version="1.0" encoding="UTF-8"?>\n<tv generator-info-name="VercelEPG">\n'
            # On définit les 5 canaux virtuels
            for i in range(1, 6):
                xml += f'  <channel id="CHOIX.{i}"><display-name>CHOIX {i}</display-name></channel>\n'
                
                if (i-1) < len(matches):
                    m = matches[i-1]
                    # Formatage temps ultra-précis
                    t_start = m['start'][:14].ljust(14, '0')
                    start = f"{t_start} +0000"
                    
                    # On calcule la fin (start + 3h)
                    dt_stop = datetime.strptime(t_start, "%Y%m%d%H%M%S") + timedelta(hours=3)
                    stop = dt_stop.strftime("%Y%m%d%H%M%S") + " +0000"

                    xml += f'  <programme start="{start}" stop="{stop}" channel="CHOIX.{i}">\n'
                    xml += f'    <title lang="fr">{m["title"]}</title>\n'
                    xml += f'    <desc lang="fr">Événement prioritaire</desc>\n'
                    xml += f'  </programme>\n'
            xml += '</tv>'
            self.wfile.write(xml.encode('utf-8'))

        # --- SORTIE M3U (La Playlist) ---
        else:
            self.send_response(200)
            self.send_header('Content-type', 'audio/x-mpegurl; charset=utf-8')
            self.end_headers()
            
            host = self.headers.get('Host')
            playlist = f'#EXTM3U x-tvg-url="https://{host}/api?type=xml"\n'
            
            for i in range(1, 6):
                if (i-1) < len(matches):
                    m = matches[i-1]
                    # Le tvg-id DOIT être identique au channel id du XML
                    playlist += f'#EXTINF:-1 tvg-id="CHOIX.{i}" tvg-name="CHOIX {i}", ⭐ {m["title"]}\n'
                    playlist += f'{STREAM_BASE}/{m["sid"]}\n'
                else:
                    playlist += f'#EXTINF:-1 tvg-id="CHOIX.{i}", CHOIX {i} (Aucun match)\n'
                    playlist += f'http://0.0.0.0\n'
            
            self.wfile.write(playlist.encode('utf-8'))
            
