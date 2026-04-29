from http.server import BaseHTTPRequestHandler
import requests
import json
import re
from datetime import datetime

JSON_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

PRIORITY_LIST = ["CANADIENS", "MONTRÉAL", "PSG", "CITY", "F1", "BLUE JAYS", "RAPTORS", "NFL", "LIVE", "EFL"]
CH_MAP = {
    "I123.15676.schedulesdirect.org": "184813",
    "I124.39080.schedulesdirect.org": "184814",
    "I111.15670.schedulesdirect.org": "184816",
    "I154.58314.schedulesdirect.org": "184821",
    "I1000.49609.schedulesdirect.org": "176800",
}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 1. Récupération et nettoyage des données
        try:
            r = requests.get(JSON_URL, timeout=5)
            match = re.search(r'\[.*\]', r.text, re.DOTALL)
            events = json.loads(match.group(0)) if match else []
        except:
            events = []

        # 2. On trie les événements par priorité
        matches = []
        for ev in events:
            title = ev.get('title', '').upper()
            ch_id = ev.get('ch')
            if ch_id in CH_MAP:
                score = 99
                for i, team in enumerate(PRIORITY_LIST):
                    if team in title:
                        score = i
                        break
                matches.append({'ev': ev, 'score': score})
        
        matches.sort(key=lambda x: x['score'])

        # --- GENERATION XMLTV (Le Guide) ---
        if "type=xml" in self.path:
            self.send_response(200)
            self.send_header('Content-type', 'application/xml; charset=utf-8')
            self.end_headers()
            
            xml = '<?xml version="1.0" encoding="UTF-8"?>\n<tv>'
            for i in range(1, 6):
                xml += f'<channel id="CHOIX.{i}"><display-name>CHOIX {i}</display-name></channel>\n'
                
            for i, m in enumerate(matches[:5]):
                ch_num = i + 1
                ev = m['ev']
                # Formatage du temps XMLTV: YYYYMMDDHHMMSS +0000
                start = ev['start'].replace(" ", "").replace("+0000", " +0000")
                # On estime une fin à +3h si manquante
                xml += f'<programme start="{start}" channel="CHOIX.{ch_num}">\n'
                xml += f'  <title lang="fr">{ev["title"]}</title>\n'
                xml += f'  <desc lang="fr">Diffusé sur {ev["name"]}</desc>\n'
                xml += f'</programme>\n'
            xml += '</tv>'
            self.wfile.write(xml.encode('utf-8'))

        # --- GENERATION M3U (La Playlist) ---
        else:
            self.send_response(200)
            self.send_header('Content-type', 'audio/x-mpegurl; charset=utf-8')
            self.end_headers()
            
            # On construit l'URL de l'EPG dynamiquement
            host = self.headers.get('Host')
            epg_url = f"http://{host}/api?type=xml"
            
            playlist = f'#EXTM3U x-tvg-url="{epg_url}"\n'
            for i in range(1, 6):
                if (i-1) < len(matches):
                    m = matches[i-1]['ev']
                    s_id = CH_MAP[m['ch']]
                    playlist += f'#EXTINF:-1 tvg-id="CHOIX.{i}" tvg-name="CHOIX {i}", CHOIX {i}\n'
                    playlist += f'{STREAM_BASE}/{s_id}\n'
                else:
                    playlist += f'#EXTINF:-1 tvg-id="CHOIX.{i}", CHOIX {i} (Vide)\n'
                    playlist += f'http://0.0.0.0\n'
            
            self.wfile.write(playlist.encode('utf-8'))
            
