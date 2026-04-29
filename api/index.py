from http.server import BaseHTTPRequestHandler
import requests
from datetime import datetime
import json
import re

JSON_URL = "[https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json](https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json)"
STREAM_BASE = "[http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV](http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV)"

TEAMS = ["CANADIENS", "CF MONTRÉAL", "BLUE JAYS", "RAPTORS", "PSG", "MANCHESTER CITY", "F1", "INTER MIAMI"]

CH_LINKS = {
    "I123.15676.schedulesdirect.org": "184813", "I124.39080.schedulesdirect.org": "184814",
    "I125.15678.schedulesdirect.org": "70935", "I154.58314.schedulesdirect.org": "184821",
    "I155.58315.schedulesdirect.org": "184822", "I111.15670.schedulesdirect.org": "184816",
    "I112.15671.schedulesdirect.org": "184817", "I113.15672.schedulesdirect.org": "184818",
    "I114.15673.schedulesdirect.org": "184819", "I115.15674.schedulesdirect.org": "184820",
    "I428.49882.gracenote.com": "71518", "I1000.49609.schedulesdirect.org": "176800",
    "I1001.104327.schedulesdirect.org": "176801", "I392.76942.gracenote.com": "157279"
}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'audio/x-mpegurl; charset=utf-8')
        self.end_headers()

        epg_data = []
        debug_msg = ""
        
        try:
            r = requests.get(JSON_URL, timeout=10)
            raw_text = r.text.strip()
            # Nettoyage agressif : on extrait tout ce qui est entre le premier [ et le dernier ]
            match = re.search(r'(\[.*\])', raw_text, re.DOTALL)
            if match:
                epg_data = json.loads(match.group(1))
            else:
                debug_msg = "Format JSON invalide (pas de crochets)"
        except Exception as e:
            debug_msg = f"Erreur: {str(e)}"

        playlist = "#EXTM3U\n"
        
        # Affichage du message d'erreur directement dans la playlist si besoin
        if debug_msg:
            playlist += f'#EXTINF:-1, !!! {debug_msg} !!!\n[http://0.0.0.0](http://0.0.0.0)\n'

        added = set()
        priority_lines = ""
        normal_lines = ""

        # 1. Détection des matchs prioritaires
        for prog in epg_data:
            title = prog.get('title', '').upper()
            ch_id = prog.get('ch')
            if ch_id in CH_LINKS and any(team in title for team in TEAMS):
                if ch_id not in added:
                    priority_lines += f'#EXTINF:-1, ⭐ {title}\n{STREAM_BASE}/{CH_LINKS[ch_id]}\n'
                    added.add(ch_id)

        # 2. Reste des chaînes
        for ch_id, stream_id in CH_LINKS.items():
            if ch_id not in added:
                name = next((p['name'] for p in epg_data if p['ch'] == ch_id), ch_id)
                normal_lines += f'#EXTINF:-1, {name}\n{STREAM_BASE}/{stream_id}\n'

        output = playlist + priority_lines + normal_lines
        self.wfile.write(output.encode('utf-8'))
        
