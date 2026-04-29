from http.server import BaseHTTPRequestHandler
import requests
import json
from datetime import datetime, timedelta

# Configuration
EPG_DATA_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

# Dictionnaire Poste -> Stream ID
STREAM_MAP = {
    "I408.18800.schedulesdirect.org": "71520",  # Sportsnet West
    "I123.15676.schedulesdirect.org": "184813", # RDS
    "I111.15670.schedulesdirect.org": "184816", # TSN
    "I154.58314.schedulesdirect.org": "184821", # TVA Sports
    "I446.52300.schedulesdirect.org": "157280", # Sky Mexico
    # ... ajoute tes autres IDs ici
}

# Pondération des priorités
FAVORITES = {
    "CANADIENS": 100, "MONTREAL": 100, "BLUE JAYS": 100, "TORONTO": 90,
    "CITY": 95, "PSG": 95, "F1": 80, "GRAND PRIX": 80,
    "HOCKEY": 50, "BASEBALL": 40, "SOCCER": 40
}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            r = requests.get(EPG_DATA_URL, timeout=10)
            raw_data = r.json()
        except:
            raw_data = []

        # 1. SCORING ET FILTRAGE
        processed_list = []
        for entry in raw_data:
            sid = STREAM_MAP.get(entry.get('ch'))
            if not sid: continue # On ignore si on n'a pas le flux vidéo
            
            # On cherche dans le titre ET la description
            search_zone = (entry.get('title', '') + " " + entry.get('desc', '')).upper()
            
            score = 10 # Score de base pour tout sport
            for key, val in FAVORITES.items():
                if key in search_zone:
                    score = max(score, val) # On garde le score le plus élevé trouvé
            
            processed_list.append({
                "title": entry.get('title'),
                "sid": sid,
                "start": entry.get('start').replace(" ", "")[:14],
                "stop": entry.get('stop').replace(" ", "")[:14],
                "score": score
            })

        # 2. TRI PAR SCORE (Favoris d'abord)
        processed_list.sort(key=lambda x: x['score'], reverse=True)

        # 3. RÉGIE : DISTRIBUTION SUR 5 CANAUX
        channels = {i: [] for i in range(1, 6)}
        for m in processed_list:
            m_start, m_stop = m['start'], m['stop']
            for i in range(1, 6):
                collision = False
                for existing in channels[i]:
                    if not (m_stop <= existing['start'] or m_start >= existing['stop']):
                        collision = True
                        break
                if not collision:
                    channels[i].append(m)
                    break

        # 4. GÉNÉRATION XMLTV
        if "type=xml" in self.path:
            self.send_response(200)
            self.send_header('Content-type', 'application/xml; charset=utf-8')
            self.end_headers()
            xml = '<?xml version="1.0" encoding="UTF-8"?><tv>'
            for i in range(1, 6):
                xml += f'<channel id="CHOIX.{i}"><display-name>CHOIX {i}</display-name></channel>'
                for prog in channels[i]:
                    xml += f'<programme start="{prog["start"]} +0000" stop="{prog["stop"]} +0000" channel="CHOIX.{i}">'
                    xml += f'<title lang="fr">{prog["title"]}</title></programme>'
            xml += '</tv>'
            self.wfile.write(xml.encode())

        # 5. GÉNÉRATION M3U
        else:
            self.send_response(200)
            self.send_header('Content-type', 'audio/x-mpegurl')
            self.end_headers()
            now = datetime.now().strftime("%Y%m%d%H%M%S")
            host = self.headers.get('Host')
            playlist = f'#EXTM3U x-tvg-url="https://{host}/api?type=xml"\n'
            for i in range(1, 6):
                stream, title = "http://0.0.0.0", "Aucun match"
                for m in channels[i]:
                    if m['start'] <= now <= m['stop']:
                        stream, title = f"{STREAM_BASE}/{m['sid']}", m['title']
                        break
                playlist += f'#EXTINF:-1 tvg-id="CHOIX.{i}", CHOIX {i} : {title}\n{stream}\n'
            self.wfile.write(playlist.encode())
            
