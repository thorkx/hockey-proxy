from http.server import BaseHTTPRequestHandler
import requests
import json
import re
from datetime import datetime, timedelta

# Configuration
EPG_DATA_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

# Dictionnaire de correspondance (Poste -> Stream ID)
STREAM_MAP = {
    "I123.15676.schedulesdirect.org": "184813", # RDS
    "I111.15670.schedulesdirect.org": "184816", # TSN
    "I154.58314.schedulesdirect.org": "184821", # TVA Sports
    "I446.52300.schedulesdirect.org": "157280", # Sky Mexico
    "I428.49882.gracenote.com": "71518",        # SN East
    "I432.49886.gracenote.com": "71522"         # SN One
}

# Poids de priorisation
PRIORITY_SCORES = {
    "CANADIENS": 100,
    "MONTREAL": 90,
    "F1": 80,
    "CITY": 70,
    "PSG": 60,
    "SOCCER": 10
}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 1. RÉCUPÉRER LA TOTALE DU BOT
        try:
            r = requests.get(EPG_DATA_URL, timeout=10)
            raw_epg = r.json()
        except:
            raw_epg = []

        # 2. ACCORDER UN SCORE ET FILTRER
        scored_matches = []
        for entry in raw_epg:
            title = entry.get('title', '').upper()
            ch_id = entry.get('ch', '')
            
            # On calcule le score
            score = 1 # Score de base
            for keyword, value in PRIORITY_SCORES.items():
                if keyword in title:
                    score = value
                    break
            
            # On cherche le SID dans notre dictionnaire
            sid = STREAM_MAP.get(ch_id)
            
            if sid: # On ne garde que si on a un flux vidéo pour ce poste
                scored_matches.append({
                    "title": entry.get('title'),
                    "sid": sid,
                    "start": entry.get('start').replace(" ", "")[:14],
                    "stop": entry.get('start').replace(" ", "")[:14], # À ajuster selon ton bot
                    "score": score
                })

        # 3. TRI PAR PRIORITÉ (Le plus gros score d'abord)
        scored_matches.sort(key=lambda x: x['score'], reverse=True)

        # 4. RÉGIE : DISTRIBUTION SUR 5 CANAUX (Éviter les chevauchements)
        channels = {1: [], 2: [], 3: [], 4: [], 5: []}
        for match in scored_matches:
            m_start = match['start']
            # On estime une durée de 3h si le bot ne donne pas de 'stop'
            m_stop = (datetime.strptime(m_start, "%Y%m%d%H%M%S") + timedelta(hours=3)).strftime("%Y%m%d%H%M%S")
            
            for i in range(1, 6):
                collision = False
                for existing in channels[i]:
                    if not (m_stop <= existing['start'] or m_start >= existing['stop']):
                        collision = True
                        break
                if not collision:
                    match['stop'] = m_stop # On fixe la fin pour le XML
                    channels[i].append(match)
                    break

        # 5. GÉNÉRATION DE LA SORTIE
        if "type=xml" in self.path:
            self.send_response(200)
            self.send_header('Content-type', 'application/xml')
            self.end_headers()
            xml = '<?xml version="1.0" encoding="UTF-8"?><tv>'
            for i in range(1, 6):
                xml += f'<channel id="CHOIX.{i}"><display-name>CHOIX {i}</display-name></channel>'
                for m in channels[i]:
                    xml += f'<programme start="{m["start"]} +0000" stop="{m["stop"]} +0000" channel="CHOIX.{i}">'
                    xml += f'<title>{m["title"]}</title></programme>'
            xml += '</tv>'
            self.wfile.write(xml.encode())
        else:
            self.send_response(200)
            self.send_header('Content-type', 'audio/x-mpegurl')
            self.end_headers()
            now = datetime.now().strftime("%Y%m%d%H%M%S")
            host = self.headers.get('Host')
            playlist = f'#EXTM3U x-tvg-url="https://{host}/api?type=xml"\n'
            for i in range(1, 6):
                stream_url = "http://0.0.0.0"
                title = "Aucun match"
                for m in channels[i]:
                    if m['start'] <= now <= m['stop']:
                        stream_url = f"{STREAM_BASE}/{m['sid']}"
                        title = m['title']
                        break
                playlist += f'#EXTINF:-1 tvg-id="CHOIX.{i}", CHOIX {i} : {title}\n{stream_url}\n'
            self.wfile.write(playlist.encode())
            
