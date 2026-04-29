from http.server import BaseHTTPRequestHandler
import requests
import json
import re
from datetime import datetime

# --- CONFIG ---
JSON_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

# Équivalence : ID de l'horaire (ESPN/EPG) -> ID du flux IPTV
EQUIVALENCE = {
    # RDS & TSN
    "I123.15676.schedulesdirect.org": "184813", # RDS 1
    "I124.39080.schedulesdirect.org": "184814", # RDS 2
    "I111.15670.schedulesdirect.org": "184816", # TSN 1
    "I154.58314.schedulesdirect.org": "184821", # TVA Sports
    
    # SPORTSNET (Ajoutés)
    "I155.58434.schedulesdirect.org": "184817", # Sportsnet East
    "I156.58435.schedulesdirect.org": "184818", # Sportsnet West
    "I157.58436.schedulesdirect.org": "184819", # Sportsnet Ontario
    "I158.58437.schedulesdirect.org": "184820", # Sportsnet Pacific
    "I159.58438.schedulesdirect.org": "184825", # Sportsnet One
    "I160.58439.schedulesdirect.org": "184826", # Sportsnet 360
    
    # INTERNATIONAUX
    "I1000.49609.schedulesdirect.org": "176800",# Sky Main Event
    "I1001.104327.schedulesdirect.org": "176801",# Sky Football
}

# Tes priorités d'équipes
PRIORITIES = ["CANADIENS", "MONTRÉAL", "PSG", "CITY", "F1", "EFL", "LIVE"]

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 1. Récupération de l'horaire filtré sur GitHub
        events = []
        try:
            r = requests.get(JSON_URL, timeout=5)
            # On nettoie le texte pour ne garder que le JSON si nécessaire
            match = re.search(r'\[.*\]', r.text, re.DOTALL)
            if match:
                events = json.loads(match.group(0))
        except Exception:
            pass

        # 2. Filtrage par disponibilité et Priorisation
        found_matches = []
        for ev in events:
            title = ev.get('title', '').upper()
            ch_id = ev.get('ch', '')
            
            # On ne garde que ce qu'on peut réellement diffuser
            if ch_id in EQUIVALENCE:
                score = 99
                for i, team in enumerate(PRIORITIES):
                    if team in title:
                        score = i
                        break
                
                found_matches.append({
                    'title': ev.get('title'),
                    'stream_id': EQUIVALENCE[ch_id],
                    'start': ev.get('start'),
                    'score': score
                })

        # Tri par score (0 = top priorité)
        found_matches.sort(key=lambda x: x['score'])

        # 3. Génération de la réponse
        if "type=xml" in self.path:
            # --- MODE EPG (Pour le guide horaire) ---
            self.send_response(200)
            self.send_header('Content-type', 'application/xml')
            self.end_headers()
            
            xml = '<?xml version="1.0" encoding="UTF-8"?><tv>'
            for i in range(1, 6):
                xml += f'<channel id="CHOIX.{i}"><display-name>CHOIX {i}</display-name></channel>'
                if (i-1) < len(found_matches):
                    m = found_matches[i-1]
                    # Formatage date ESPN vers standard XMLTV
                    start_fix = m['start'].replace(" ", "").replace("+0000", " +0000")
                    xml += f'<programme start="{start_fix}" channel="CHOIX.{i}"><title>{m["title"]}</title></programme>'
            xml += '</tv>'
            self.wfile.write(xml.encode('utf-8'))

        else:
            # --- MODE M3U (Le Stream Direct) ---
            self.send_response(200)
            self.send_header('Content-type', 'audio/x-mpegurl')
            self.end_headers()
            
            host = self.headers.get('Host')
            playlist = f'#EXTM3U x-tvg-url="http://{host}/api?type=xml"\n'
            
            for i in range(1, 6):
                if (i-1) < len(found_matches):
                    m = found_matches[i-1]
                    playlist += f'#EXTINF:-1 tvg-id="CHOIX.{i}", CHOIX {i} : {m["title"]}\n'
                    playlist += f'{STREAM_BASE}/{m["stream_id"]}\n'
                else:
                    playlist += f'#EXTINF:-1 tvg-id="CHOIX.{i}", CHOIX {i} (Aucun match)\n'
                    playlist += f'http://0.0.0.0\n'
            
            self.wfile.write(playlist.encode('utf-8'))
            
