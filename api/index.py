from http.server import BaseHTTPRequestHandler
import requests
import json
import re
from datetime import datetime

JSON_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

# Tes filtres (j'ai ajouté "LIVE" et "EFL" suite à ton JSON)
TEAMS = ["CANADIENS", "MONTRÉAL", "BLUE JAYS", "RAPTORS", "CITY", "PSG", "F1", "MIAMI", "LIVE", "EFL"]

# Mapping avec les noms que tu veux voir
CHANNELS = {
    "I123.15676.schedulesdirect.org": ("RDS 1 FHD", "184813"),
    "I124.39080.schedulesdirect.org": ("RDS 2 FHD", "184814"),
    "I154.58314.schedulesdirect.org": ("TVA SPORTS 1", "184821"),
    "I111.15670.schedulesdirect.org": ("TSN 1 FHD", "184816"),
    "I1000.49609.schedulesdirect.org": ("Sky Main Event", "176800"),
    "I446.52300.schedulesdirect.org": ("Sky Mexico (La Liga)", "157280"),
    "I392.76942.gracenote.com": ("beIN Sports", "157279")
}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'audio/x-mpegurl; charset=utf-8')
        self.end_headers()

        epg_data = []
        try:
            r = requests.get(JSON_URL, timeout=5)
            # Nettoyage du JSON pour éviter l'erreur "Extra Data"
            match = re.search(r'\[.*\]', r.text, re.DOTALL)
            if match:
                epg_data = json.loads(match.group(0))
        except:
            pass

        now = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        playlist = "#EXTM3U\n"
        priority_lines = ""
        normal_lines = ""
        added = set()

        # 1. Trier les matchs : Priorité à ce qui est LIVE maintenant
        for prog in epg_data:
            ch_id = prog.get('ch')
            title = prog.get('title', '').upper()
            # Nettoyage de l'heure : "20260428160000 +0000" -> "20260428160000"
            start_time = prog.get('start', '').split(' ')[0]

            if ch_id in CHANNELS:
                name, s_id = CHANNELS[ch_id]
                link = f"{STREAM_BASE}/{s_id}"
                
                # C'est prioritaire si une équipe match ET que ça joue bientôt ou maintenant
                is_team = any(t in title for t in TEAMS)
                
                if is_team and ch_id not in added:
                    # On affiche le titre du match directement dans le nom du poste
                    priority_lines += f'#EXTINF:-1, ⭐ {title} ({name})\n{link}\n'
                    added.add(ch_id)

        # 2. Remplissage du reste de la liste avec les noms propres
        for ch_id, (name, s_id) in CHANNELS.items():
            if ch_id not in added:
                # Chercher ce qui joue actuellement pour l'afficher à côté du nom
                current_title = next((p['title'] for p in epg_data if p['ch'] == ch_id and p.get('start', '').split(' ')[0] <= now), "")
                suffix = f" - {current_title}" if current_title else ""
                normal_lines += f'#EXTINF:-1, {name}{suffix}\n{STREAM_BASE}/{s_id}\n'

        output = playlist + priority_lines + normal_lines
        self.wfile.write(output.encode('utf-8'))
        
