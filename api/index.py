from http.server import BaseHTTPRequestHandler
import requests
import json
import re

# Ton URL GitHub (vérifie bien qu'elle est publique)
JSON_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

TEAMS = ["CANADIENS", "MONTRÉAL", "BLUE JAYS", "RAPTORS", "CITY", "PSG", "F1", "MIAMI"]

# Mapping simplifié mais complet pour tester
CHANNELS = {
    "I123.15676.schedulesdirect.org": ("RDS FHD", "184813"),
    "I124.39080.schedulesdirect.org": ("RDS 2 FHD", "184814"),
    "I154.58314.schedulesdirect.org": ("TVA SPORTS FHD", "184821"),
    "I111.15670.schedulesdirect.org": ("TSN 1 FHD", "184816"),
    "I428.49882.gracenote.com": ("Sportsnet East", "71518"),
    "I1000.49609.schedulesdirect.org": ("Sky Main Event", "176800"),
    "I1001.104327.schedulesdirect.org": ("Sky Football", "176801")
}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'audio/x-mpegurl; charset=utf-8')
        self.end_headers()

        epg_data = []
        error_log = ""

        # 1. RÉCUPÉRATION DU JSON AVEC NETTOYAGE AGRESSIF
        try:
            r = requests.get(JSON_URL, timeout=5)
            text = r.text
            # On cherche uniquement ce qui est entre [ et ]
            match = re.search(r'\[.*\]', text, re.DOTALL)
            if match:
                epg_data = json.loads(match.group(0))
            else:
                error_log = "Format JSON invalide"
        except Exception as e:
            error_log = f"Erreur: {str(e)}"

        playlist = "#EXTM3U\n"
        
        # 2. LOG D'ERREUR DANS LA PLAYLIST (si ça arrive)
        if error_log:
            playlist += f"#EXTINF:-1, !!! {error_log} !!!\nhttp://0.0.0.0\n"

        added = set()
        priority_lines = ""
        normal_lines = ""

        # 3. FILTRAGE DES MATCHS (On compare avec le JSON)
        for prog in epg_data:
            ch_id = prog.get('ch')
            title = prog.get('title', '').upper()
            
            if ch_id in CHANNELS:
                name, s_id = CHANNELS[ch_id]
                if any(t in title for t in TEAMS) and ch_id not in added:
                    priority_lines += f"#EXTINF:-1, ⭐ LIVE: {title} ({name})\n{STREAM_BASE}/{s_id}\n"
                    added.add(ch_id)

        # 4. AJOUT DU RESTE (Fallback pour toujours avoir des postes)
        for ch_id, (name, s_id) in CHANNELS.items():
            if ch_id not in added:
                normal_lines += f"#EXTINF:-1, {name}\n{STREAM_BASE}/{s_id}\n"

        output = playlist + priority_lines + normal_lines
        self.wfile.write(output.encode('utf-8'))
        
