from http.server import BaseHTTPRequestHandler
import requests
import json
import re
from datetime import datetime

# URL de ton JSON enrichi
EPG_DATA_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

# Assure-toi que ces IDs sont EXACTEMENT comme dans ton JSON
STREAM_MAP = {
    "I408.18800.schedulesdirect.org": "71520",
    "I123.15676.schedulesdirect.org": "184813",
    "I446.52300.schedulesdirect.org": "157280"
}

FAVORITES = {"CANADIENS": 100, "BLUE JAYS": 100, "CITY": 95, "F1": 80}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            r = requests.get(EPG_DATA_URL, timeout=10)
            raw_data = r.json()
        except Exception as e:
            raw_data = []

        processed_list = []
        for entry in raw_data:
            ch_id = entry.get('ch')
            sid = STREAM_MAP.get(ch_id, "184813") # RDS par défaut pour le test
            
            # NETTOYAGE DES DATES : On ne garde que les 14 premiers chiffres
            raw_start = entry.get('start', '').replace(" ", "")[:14]
            raw_stop = entry.get('stop', '').replace(" ", "")[:14]
            
            if len(raw_start) < 14: continue

            # Scoring
            search_zone = (entry.get('title', '') + " " + entry.get('desc', '')).upper()
            score = 10
            for key, val in FAVORITES.items():
                if key in search_zone:
                    score = max(score, val)
            
            processed_list.append({
                "title": entry.get('title'),
                "sid": sid,
                "start": raw_start,
                "stop": raw_stop,
                "score": score
            })

        # Tri par score
        processed_list.sort(key=lambda x: x['score'], reverse=True)

        # Distribution sur 5 canaux
        channels = {i: [] for i in range(1, 6)}
        for m in processed_list:
            for i in range(1, 6):
                collision = False
                for existing in channels[i]:
                    # Logique de collision simplifiée
                    if not (m['stop'] <= existing['start'] or m['start'] >= existing['stop']):
                        collision = True
                        break
                if not collision:
                    channels[i].append(m)
                    break

        if "type=xml" in self.path:
            self.send_response(200)
            self.send_header('Content-type', 'application/xml; charset=utf-8')
            self.end_headers()
            xml = '<?xml version="1.0" encoding="UTF-8"?><tv>'
            for i in range(1, 6):
                xml += f'<channel id="CHOIX.{i}"><display-name>CHOIX {i}</display-name></channel>'
                for prog in channels[i]:
                    # On rajoute le fuseau pour le format XMLTV standard
                    s, t = prog['start'] + " +0000", prog['stop'] + " +0000"
                    xml += f'<programme start="{s}" stop="{t}" channel="CHOIX.{i}">'
                    xml += f'<title lang="fr">{prog["title"]}</title></programme>'
            xml += '</tv>'
            self.wfile.write(xml.encode('utf-8'))
        else:
            self.send_response(200)
            self.send_header('Content-type', 'audio/x-mpegurl')
            self.end_headers()
            # Utilise l'heure actuelle SANS fuseau pour comparer avec le JSON nettoyé
            now = datetime.utcnow().strftime("%Y%m%d%H%M%S")
            host = self.headers.get('Host')
            playlist = f'#EXTM3U x-tvg-url="https://{host}/api?type=xml"\n'
            for i in range(1, 6):
                stream, title = "http://0.0.0.0", "Aucun match"
                for m in channels[i]:
                    if m['start'] <= now <= m['stop']:
                        stream, title = f"{STREAM_BASE}/{m['sid']}", m['title']
                        break
                playlist += f'#EXTINF:-1 tvg-id="CHOIX.{i}", CHOIX {i} : {title}\n{stream}\n'
            self.wfile.write(playlist.encode('utf-8'))
            
