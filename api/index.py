from http.server import BaseHTTPRequestHandler
import requests
from datetime import datetime

# URL brute de ton JSON sur GitHub
JSON_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
# Ta base de serveur extraite de ta playlist
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

# Tes équipes prioritaires
TEAMS = ["CANADIENS", "CF MONTRÉAL", "BLUE JAYS", "RAPTORS", "PSG", "MANCHESTER CITY", "F1"]

# Le mapping strict entre EPG et ton IPTV
CHANNELS = {
    "I123.15676.schedulesdirect.org": ("RDS FHD", "184813"),
    "I124.39080.schedulesdirect.org": ("RDS 2 FHD", "184814"),
    "I111.15670.schedulesdirect.org": ("TSN 1 FHD", "184816"),
    "I112.15671.schedulesdirect.org": ("TSN 2 FHD", "184817"),
    "I154.58314.schedulesdirect.org": ("TVA SPORTS FHD", "184821"),
    "I155.58315.schedulesdirect.org": ("TVA SPORTS 2 FHD", "184822"),
    "I1000.49609.schedulesdirect.org": ("SKY MAIN EVENT", "176800"),
    "I1001.104327.schedulesdirect.org": ("SKY FOOTBALL", "176801")
}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8') # On force le texte pour débugger
        self.end_headers()

        # 1. On tente de lire le JSON
        epg_data = []
        try:
            r = requests.get(JSON_URL, timeout=5)
            epg_data = r.json()
        except Exception as e:
            self.wfile.write(f"# ERREUR CHARGEMENT JSON: {e}\n".encode())

        now = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        
        output = "#EXTM3U\n"
        priority_lines = ""
        all_lines = ""
        added = set()

        # 2. On scanne le JSON pour les matchs
        for prog in epg_data:
            title = prog.get('title', '').upper()
            ch_id = prog.get('ch')
            
            if ch_id in CHANNELS:
                name, stream_id = CHANNELS[ch_id]
                link = f"{STREAM_BASE}/{stream_id}"
                
                # Si une équipe joue
                if any(t in title for t in TEAMS):
                    if ch_id not in added:
                        priority_lines += f'#EXTINF:-1, ⭐ LIVE: {title}\n{link}\n'
                        added.add(ch_id)
                else:
                    # Sinon on l'ajoute à la liste normale (si pas déjà ajoutée)
                    if ch_id not in added:
                        all_lines += f'#EXTINF:-1, {name}\n{link}\n'
                        added.add(ch_id)

        output += priority_lines + all_lines
        self.wfile.write(output.encode('utf-8'))
        
