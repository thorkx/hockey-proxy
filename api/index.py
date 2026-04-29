from http.server import BaseHTTPRequestHandler
import requests
import json
from datetime import datetime

# CONFIGURATION
URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

# Poids de priorité pour tes favoris
PRIORITIES = {
    "CANADIENS": 1000, "MONTREAL": 900, "JAYS": 800, "BLUE JAYS": 800,
    "CITY": 700, "PSG": 650, "F1": 600, "GRAND PRIX": 600
}

# Mapping ID Bot -> Stream ID (Ajuste avec tes vrais IDs)
STREAM_MAP = {
    "I408.18800.schedulesdirect.org": "71520",
    "I123.15676.schedulesdirect.org": "184813",
    "I111.15670.schedulesdirect.org": "184816",
    "I154.58314.schedulesdirect.org": "184821",
    "I446.52300.schedulesdirect.org": "157280"
}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            r = requests.get(URL, headers={'Cache-Control': 'no-cache'}, timeout=10)
            data = r.json()
        except:
            data = []

        # 1. SCORING & NETTOYAGE
        scored = []
        for e in data:
            title_desc = (e.get('title', '') + " " + e.get('desc', '')).upper()
            score = 10
            for key, val in PRIORITIES.items():
                if key in title_desc:
                    score = val
                    break
            
            scored.append({
                "title": e.get('title', 'Sport'),
                "sid": STREAM_MAP.get(e.get('ch'), "184813"),
                "start": e.get('start', '').replace(" ", "")[:14],
                "stop": e.get('stop', '').replace(" ", "")[:14],
                "score": score
            })

        # 2. TRI ET RÉGIE (Distribution anti-conflit sur 5 canaux)
        scored.sort(key=lambda x: x['score'], reverse=True)
        channels = {i: [] for i in range(1, 6)}
        
        for m in scored:
            for i in range(1, 6):
                collision = any(not (m['stop'] <= ex['start'] or m['start'] >= ex['stop']) for ex in channels[i])
                if not collision:
                    channels[i].append(m)
                    break

        # 3. SORTIE XML OU M3U
        self.send_response(200)
        if "type=xml" in self.path:
            self.send_header('Content-type', 'application/xml; charset=utf-8')
            self.end_headers()
            xml = '<?xml version="1.0" encoding="UTF-8"?><tv>'
            for i in range(1, 6):
                xml += f'<channel id="CHOIX.{i}"><display-name>CHOIX {i}</display-name></channel>'
                for p in channels[i]:
                    xml += f'<programme start="{p["start"]} +0000" stop="{p["stop"]} +0000" channel="CHOIX.{i}"><title>{p["title"]}</title></programme>'
            self.wfile.write((xml + '</tv>').encode('utf-8'))
        else:
            self.send_header('Content-type', 'audio/x-mpegurl')
            self.end_headers()
            now = datetime.utcnow().strftime("%Y%m%d%H%M%S")
            m3u = f'#EXTM3U x-tvg-url="https://{self.headers.get("Host")}/api?type=xml"\n'
            for i in range(1, 6):
                stream, title = "http://0.0.0.0", "Aucun match"
                for m in channels[i]:
                    if m['start'] <= now <= m['stop']:
                        stream, title = f"{STREAM_BASE}/{m['sid']}", m['title']
                        break
                m3u += f'#EXTINF:-1 tvg-id="CHOIX.{i}", CHOIX {i} : {title}\n{stream}\n'
            self.wfile.write(m3u.encode('utf-8'))
            
