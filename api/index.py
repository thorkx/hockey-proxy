from http.server import BaseHTTPRequestHandler
import requests
import json
import re

JSON_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

# Équipes pour les étoiles
TEAMS = ["CANADIENS", "MONTRÉAL", "BLUE JAYS", "RAPTORS", "CITY", "PSG", "F1", "MIAMI"]

# MAPPING DEFINITIF (Nom affiché, ID de flux)
CHANNELS = {
    "I123.15676.schedulesdirect.org": ("RDS 1 FHD", "184813"),
    "I124.39080.schedulesdirect.org": ("RDS 2 FHD", "184814"),
    "I154.58314.schedulesdirect.org": ("TVA SPORTS 1 FHD", "184821"),
    "I155.58315.schedulesdirect.org": ("TVA SPORTS 2 FHD", "184822"),
    "I111.15670.schedulesdirect.org": ("TSN 1 FHD", "184816"),
    "I112.15671.schedulesdirect.org": ("TSN 2 FHD", "184817"),
    "I113.15672.schedulesdirect.org": ("TSN 3 FHD", "184818"),
    "I114.15673.schedulesdirect.org": ("TSN 4 FHD", "184819"),
    "I115.15674.schedulesdirect.org": ("TSN 5 FHD", "184820"),
    "I428.49882.gracenote.com": ("Sportsnet East", "71518"),
    "I432.49886.gracenote.com": ("Sportsnet One", "71522"),
    "I1000.49609.schedulesdirect.org": ("Sky Sports Main Event", "176800"),
    "I1001.104327.schedulesdirect.org": ("Sky Sports Football", "176801"),
    "I207.12447.schedulesdirect.org": ("DAZN 1", "176814"),
    "I208.12448.schedulesdirect.org": ("DAZN 2", "176815")
}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'audio/x-mpegurl; charset=utf-8')
        self.end_headers()

        epg_data = []
        try:
            r = requests.get(JSON_URL, timeout=5)
            # Nettoyage pour extraire le JSON même si entouré de texte
            match = re.search(r'(\[.*\])', r.text, re.DOTALL)
            if match:
                epg_data = json.loads(match.group(1))
        except:
            pass

        playlist = "#EXTM3U\n"
        added = set()
        priority_lines = ""
        normal_lines = ""

        # 1. On cherche les matchs prioritaires dans le JSON
        for prog in epg_data:
            ch_id = prog.get('ch')
            title = prog.get('title', '').upper()
            
            if ch_id in CHANNELS:
                name, s_id = CHANNELS[ch_id]
                if any(t in title for t in TEAMS) and ch_id not in added:
                    priority_lines += f'#EXTINF:-1, ⭐ {title} ({name})\n{STREAM_BASE}/{s_id}\n'
                    added.add(ch_id)

        # 2. On ajoute TOUTES les chaînes avec leurs VRAIS NOMS
        for ch_id, (name, s_id) in CHANNELS.items():
            if ch_id not in added:
                normal_lines += f'#EXTINF:-1, {name}\n{STREAM_BASE}/{s_id}\n'

        output = playlist + priority_lines + normal_lines
        self.wfile.write(output.encode('utf-8'))
        
