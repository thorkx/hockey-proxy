from http.server import BaseHTTPRequestHandler
import requests
from datetime import datetime
import json
import re

# Configuration
JSON_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

# Tes équipes (Priorité 1 et 2)
TEAMS = ["CANADIENS", "CF MONTRÉAL", "BLUE JAYS", "RAPTORS", "MANCHESTER CITY", "PSG", "BOLOGNE", "WREXHAM", "F1", "INTER MIAMI", "LAKERS", "OILERS"]

# Mapping complet extrait de ta playlist
CH_LINKS = {
    # Québec
    "I123.15676.schedulesdirect.org": "184813",  # RDS FHD
    "I124.39080.schedulesdirect.org": "184814",  # RDS 2 FHD
    "I125.15678.schedulesdirect.org": "70935",   # RDS INFO
    "I154.58314.schedulesdirect.org": "184821",  # TVA SPORTS FHD
    "I155.58315.schedulesdirect.org": "184822",  # TVA SPORTS 2 FHD
    # TSN & Sportsnet
    "I111.15670.schedulesdirect.org": "184816",  # TSN 1
    "I112.15671.schedulesdirect.org": "184817",  # TSN 2
    "I113.15672.schedulesdirect.org": "184818",  # TSN 3
    "I114.15673.schedulesdirect.org": "184819",  # TSN 4
    "I115.15674.schedulesdirect.org": "184820",  # TSN 5
    "I428.49882.gracenote.com": "71518",         # Sportsnet East
    # DAZN & Apple MLS
    "I207.12447.schedulesdirect.org": "176814",  # DAZN 1
    "I208.12448.schedulesdirect.org": "176815",  # DAZN 2
    "MLS.1": "176901", "MLS.2": "176902", "MLS.3": "176903",
    # Europe
    "I1000.49609.schedulesdirect.org": "176800", # Sky Main Event
    "I1001.104327.schedulesdirect.org": "176801",# Sky Football
    "I392.76942.gracenote.com": "157279",        # beIN 1
}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'audio/x-mpegurl; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        # 1. Récupération et nettoyage forcé du JSON
        epg_data = []
        try:
            r = requests.get(JSON_URL, timeout=10)
            raw_text = r.text.strip()
            # On cherche le premier '[' et le dernier ']' pour extraire le JSON pur
            match = re.search(r'(\[.*\])', raw_text, re.DOTALL)
            if match:
                epg_data = json.loads(match.group(1))
        except:
            pass

        now = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        playlist = "#EXTM3U\n"
        priority_lines = ""
        normal_lines = ""
        added = set()

        # 2. Construction de la logique de priorité
        # On regarde d'abord les matchs en direct
        for prog in epg_data:
            title = prog.get('title', '').upper()
            ch_id = prog.get('ch')
            
            if ch_id in CH_LINKS:
                stream_id = CH_LINKS[ch_id]
                link = f"{STREAM_BASE}/{stream_id}"
                
                # Si une de tes équipes est dans le titre
                if any(team in title for team in TEAMS):
                    if ch_id not in added:
                        priority_lines += f'#EXTINF:-1, ⭐ LIVE: {title} ({prog.get("name")})\n{link}\n'
                        added.add(ch_id)

        # 3. Ajout du reste des postes pour ne rien perdre
        for ch_id, stream_id in CH_LINKS.items():
            if ch_id not in added:
                # On essaie de trouver le nom du poste dans le JSON pour l'affichage
                display_name = next((p['name'] for p in epg_data if p['ch'] == ch_id), ch_id)
                normal_lines += f'#EXTINF:-1, {display_name}\n{STREAM_BASE}/{stream_id}\n'

        # 4. Assemblage final
        if priority_lines:
            playlist += "\n# --- MATCHS PRIORITAIRES ---\n" + priority_lines
        
        playlist += "\n# --- TOUTES LES CHAÎNES ---\n" + normal_lines
        
        self.wfile.write(playlist.encode('utf-8'))
        
