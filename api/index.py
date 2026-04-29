from http.server import BaseHTTPRequestHandler
import requests
import json
import re
from datetime import datetime, timedelta

JSON_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

# ÉQUIVALENCE (Vérifie bien que ces IDs sont dans ton filtered_epg.json)
MAP = {
    "I123.15676.schedulesdirect.org": "184813",
    "I124.39080.schedulesdirect.org": "184814",
    "I111.15670.schedulesdirect.org": "184816",
    "I154.58314.schedulesdirect.org": "184821",
    "I1000.49609.schedulesdirect.org": "176800",
    "I1001.104327.schedulesdirect.org": "176801",
    "I446.52300.schedulesdirect.org": "157280",
    "I428.49882.gracenote.com": "71518",
    "I432.49886.gracenote.com": "71522"
}

PRIORITIES = ["CANADIENS", "MONTRÉAL", "PSG", "CITY", "F1", "EFL", "LIVE"]

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        events = []
        try:
            r = requests.get(JSON_URL, timeout=5)
            # On cherche le JSON n'importe où dans la réponse
            data_match = re.search(r'\[.*\]', r.text, re.DOTALL)
            if data_match:
                events = json.loads(data_match.group(0))
        except:
            pass

        matches = []
        for e in events:
            ch_id = str(e.get('ch', '')).strip()
            # On cherche si l'ID est dans notre MAP
            if ch_id in MAP:
                title = e.get('title', 'Sport').upper()
                score = next((i for i, t in enumerate(PRIORITIES) if t in title), 99)
                matches.append({
                    'title': e.get('title'),
                    'sid': MAP[ch_id],
                    'start': e.get('start', '').replace(" ", "").replace("+0000", ""),
                    'score': score,
                    'ch_id': ch_id
                })

        # --- FALLBACK DEBUG ---
        # Si aucun match trouvé avec la MAP, on prend les 5 premiers du JSON 
        # pour forcer l'affichage de l'EPG et voir ce qui cloche
        if not matches and events:
            for e in events[:5]:
                matches.append({
                    'title': f"[DEBUG] {e.get('title')}",
                    'sid': "184813", # RDS par défaut pour le test
                    'start': e.get('start', '').replace(" ", "").replace("+0000", ""),
                    'score': 100,
                    'ch_id': e.get('ch')
                })

        matches.sort(key=lambda x: x['score'])

        if "type=xml" in self.path:
            self.send_response(200)
            self.send_header('Content-type', 'application/xml; charset=utf-8')
            self.end_headers()
            xml = '<?xml version="1.0" encoding="UTF-8"?>\n<tv>\n'
            for i in range(1, 6):
                xml += f'  <channel id="CHOIX.{i}"><display-name>CHOIX {i}</display-name></channel>\n'
                if (i-1) < len(matches):
                    m = matches[i-1]
                    t_val = m['start'][:14].ljust(14, '0')
                    start = f"{t_val} +0000"
                    # Stop +4h
                    dt_stop = datetime.strptime(t_val, "%Y%m%d%H%M%S") + timedelta(hours=4)
                    stop = dt_stop.strftime("%Y%m%d%H%M%S") + " +0000"
                    xml += f'  <programme start="{start}" stop="{stop}" channel="CHOIX.{i}">\n'
                    xml += f'    <title lang="fr">{m["title"]}</title>\n'
                    xml += f'    <desc lang="fr">Source ID: {m["ch_id"]}</desc>\n'
                    xml += f'  </programme>\n'
            xml += '</tv>'
            self.wfile.write(xml.encode('utf-8'))
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
                    playlist += f'#EXTINF:-1 tvg-id="CHOIX.{i}", CHOIX {i} (Vide)\n'
                    playlist += f'http://0.0.0.0\n'
            self.wfile.write(playlist.encode('utf-8'))
            
