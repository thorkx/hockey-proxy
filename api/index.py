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
        # 1. Récupération des données
        r = requests.get(JSON_URL)
        match = re.search(r'\[.*\]', r.text, re.DOTALL)
        events = json.loads(match.group(0)) if match else []

        # 2. Tri des matchs par priorité
        active_matches = []
        for ev in events:
            title = ev.get('title', '').upper()
            if ev.get('ch') in CH_MAP:
                score = next((i for i, t in enumerate(PRIORITY_LIST) if t in title), 99)
                active_matches.append({'ev': ev, 'score': score})
        active_matches.sort(key=lambda x: x['score'])

        # 3. Réponse selon le type demandé
        if "type=xml" in self.path:
            self.send_response(200)
            self.send_header('Content-type', 'application/xml')
            self.end_headers()
            xml = '<?xml version="1.0" encoding="UTF-8"?><tv>'
            for i in range(1, 4):
                xml += f'<channel id="CHOIX.{i}"><display-name>CHOIX {i}</display-name></channel>'
                if (i-1) < len(active_matches):
                    m = active_matches[i-1]['ev']
                    # On convertit le temps du JSON pour le XMLTV
                    start = m['start'].replace(" +0000", " +0000").replace(" ", "")
                    xml += f'<programme start="{start}" channel="CHOIX.{i}">'
                    xml += f'<title>{m["title"]}</title><desc>Source: {m["name"]}</desc></programme>'
            xml += '</tv>'
            self.wfile.write(xml.encode('utf-8'))
        
        else:
            self.send_response(200)
            self.send_header('Content-type', 'audio/x-mpegurl')
            self.end_headers()
            playlist = "#EXTM3U x-tvg-url=\"" + "http://" + self.headers.get('Host') + "/api?type=xml\"\n"
            for i in range(1, 4):
                if (i-1) < len(active_matches):
                    m = active_matches[i-1]['ev']
                    playlist += f'#EXTINF:-1 tvg-id="CHOIX.{i}", CHOIX {i}\n'
                    playlist += f'{STREAM_BASE}/{CH_MAP[m["ch"]]}\n'
            self.wfile.write(playlist.encode('utf-8'))
            
