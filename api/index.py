from http.server import BaseHTTPRequestHandler
import requests
from datetime import datetime
import json
import re

JSON_URL = "[https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json](https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json)"
STREAM_BASE = "[http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV](http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV)"

TEAMS = ["CANADIENS", "CF MONTRÉAL", "BLUE JAYS", "RAPTORS", "PSG", "MANCHESTER CITY", "F1", "INTER MIAMI"]

CHANNELS = {
    "I123.15676.schedulesdirect.org": ("RDS FHD", "184813"),
    "I124.39080.schedulesdirect.org": ("RDS 2 FHD", "184814"),
    "I111.15670.schedulesdirect.org": ("TSN 1 FHD", "184816"),
    "I112.15671.schedulesdirect.org": ("TSN 2 FHD", "184817"),
    "I154.58314.schedulesdirect.org": ("TVA SPORTS FHD", "184821"),
    "I155.58315.schedulesdirect.org": ("TVA SPORTS 2 FHD", "184822"),
}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        # On remet le type mpegurl pour ton app IPTV
        self.send_header('Content-type', 'audio/x-mpegurl; charset=utf-8')
        self.end_headers()

        epg_data = []
        try:
            r = requests.get(JSON_URL, timeout=5)
            content = r.text.strip()
            
            # NETTOYAGE : On enlève tout ce qui n'est pas entre les crochets [ ]
            # Ça règle l'erreur "Extra data" si ton bot a écrit du texte autour du JSON
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                epg_data = json.loads(json_match.group(0))
            else:
                epg_data = json.loads(content)
        except Exception as e:
            self.wfile.write(f"# ERREUR JSON: {str(e)}\n".encode())
            return

        playlist = "#EXTM3U\n"
        priority_lines = ""
        all_lines = ""
        added = set()

        for prog in epg_data:
            title = prog.get('title', '').upper()
            ch_id = prog.get('ch')
            
            if ch_id in CHANNELS:
                name, stream_id = CHANNELS[ch_id]
                link = f"{STREAM_BASE}/{stream_id}"
                
                if any(t in title for t in TEAMS) and ch_id not in added:
                    priority_lines += f'#EXTINF:-1, ⭐ {title} ({name})\n{link}\n'
                    added.add(ch_id)

        # Ajout du reste des chaînes mappées
        for ch_id, (name, stream_id) in CHANNELS.items():
            if ch_id not in added:
                all_lines += f'#EXTINF:-1, {name}\n{STREAM_BASE}/{stream_id}\n'

        output = playlist + priority_lines + all_lines
        self.wfile.write(output.encode('utf-8'))
        
