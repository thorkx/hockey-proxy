from http.server import BaseHTTPRequestHandler
import requests
import json
from datetime import datetime

# CONFIGURATION
URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

# PRIORITÉS : Plus le score est haut, plus le match monte vers CHOIX 1
PRIORITIES = {
    "CANADIENS": 1000, "MONTREAL": 900, "JAYS": 800, "BLUE JAYS": 800,
    "CITY": 700, "PSG": 650, "F1": 600, "GRAND PRIX": 600
}

# MAPPING : ID du Bot -> ID de ton flux IPTV
STREAM_MAP = {
    "I408.18800.schedulesdirect.org": "71520", # Sportsnet West
    "I123.15676.schedulesdirect.org": "184813", # RDS
    "I111.15670.schedulesdirect.org": "184816", # TSN
    "I154.58314.schedulesdirect.org": "184821", # TVA Sports
    "I446.52300.schedulesdirect.org": "157280"  # Sky Mexico
}

def clean_xml(text):
    """Empêche le crash du XML en nettoyant les caractères spéciaux comme &"""
    if not text: return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;")

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 1. RÉCUPÉRATION DU JSON DEPUIS GITHUB
        try:
            r = requests.get(URL, headers={'Cache-Control': 'no-cache'}, timeout=10)
            data = r.json()
        except:
            data = []

        # 2. SCORING & NETTOYAGE DES DONNÉES
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
                "sid": STREAM_MAP.get(e.get('ch'), "184813"), # RDS par défaut si non mappé
                "start": e.get('start', '').replace(" ", "")[:14],
                "stop": e.get('stop', '').replace(" ", "")[:14],
                "score": score
            })

        # 3. RÉGIE : DISTRIBUTION SUR 5 CANAUX (Tri par priorité)
        scored.sort(key=lambda x: x['score'], reverse=True)
        channels = {i: [] for i in range(1, 6)}
        
        for m in scored:
            if len(m['start']) < 14: continue # Skip si date invalide
            for i in range(1, 6):
                collision = any(not (m['stop'] <= ex['start'] or m['start'] >= ex['stop']) for ex in channels[i])
                if not collision:
                    channels[i].append(m)
                    break

        # 4. GÉNÉRATION DE LA SORTIE
        self.send_response(200)
        
        # MODE XML (EPG)
        if "type=xml" in self.path:
            self.send_header('Content-type', 'application/xml; charset=utf-8')
            self.end_headers()
            xml = '<?xml version="1.0" encoding="UTF-8"?><tv>'
            for i in range(1, 6):
                xml += f'<channel id="CHOIX.{i}"><display-name>CHOIX {i}</display-name></channel>'
                for p in channels[i]:
                    safe_title = clean_xml(p["title"])
                    xml += f'<programme start="{p["start"]} +0000" stop="{p["stop"]} +0000" channel="CHOIX.{i}">'
                    xml += f'<title lang="fr">{safe_title}</title></programme>'
            self.wfile.write((xml + '</tv>').encode('utf-8'))
        
        # MODE M3U (Playlist)
        else:
            self.send_header('Content-type', 'audio/x-mpegurl')
            self.end_headers()
            now = datetime.utcnow().strftime("%Y%m%d%H%M%S")
            host = self.headers.get('Host', 'localhost')
            m3u = f'#EXTM3U x-tvg-url="https://{host}/api?type=xml"\n'
            for i in range(1, 6):
                stream_url, current_title = "http://0.0.0.0", "Aucun match"
                for m in channels[i]:
                    if m['start'] <= now <= m['stop']:
                        stream_url, current_title = f"{STREAM_BASE}/{m['sid']}", m['title']
                        break
                m3u += f'#EXTINF:-1 tvg-id="CHOIX.{i}", CHOIX {i} : {current_title}\n{stream_url}\n'
            self.wfile.write(m3u.encode('utf-8'))
            
