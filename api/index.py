from http.server import BaseHTTPRequestHandler
import requests
import json
from datetime import datetime, timedelta

# CONFIGURATION
BIBLE_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

# Les ligues à surveiller
LEAGUES = [
    ("hockey", "nhl"),
    ("baseball", "mlb"),
    ("soccer", "eng.1"), # Premier League
    ("soccer", "fra.1")  # Ligue 1
]

STREAM_MAP = {
    "I408.18800.schedulesdirect.org": "71520",
    "I123.15676.schedulesdirect.org": "184813",
    "I111.15670.schedulesdirect.org": "184816",
    "I154.58314.schedulesdirect.org": "184821"
}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 1. CHARGER LA BIBLE (Une seule fois)
        try:
            bible = requests.get(BIBLE_URL, timeout=10).json()
        except:
            bible = []

        final_selection = []
        now = datetime.utcnow()

        # 2. BOUCLER SUR LES 4 PROCHAINS JOURS
        for day_offset in range(4):
            target_date = (now + timedelta(days=day_offset)).strftime("%Y%m%d")
            
            for sport, league in LEAGUES:
                # API ESPN Schedule pour une date précise
                url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard?dates={target_date}"
                try:
                    res = requests.get(url, timeout=5).json()
                    events = res.get('events', [])
                    
                    for event in events:
                        name = event.get('name', '').upper()
                        # Date de début ESPN (format ISO)
                        start_iso = event.get('date', '') 
                        # On simplifie pour comparer avec la bible (YYYYMMDDHH)
                        match_time_key = start_iso.replace('-', '').replace(':', '').replace('T', '')[:10]

                        # 3. TROUVER LE FLUX DANS LA BIBLE
                        # On cherche un programme qui contient une équipe du match à la même heure
                        found_ch = None
                        teams = name.replace(' AT ', ' ').replace(' @ ', ' ').split(' ')
                        
                        for prog in bible:
                            prog_start = prog.get('start', '').replace(" ", "")[:10]
                            if prog_start == match_time_key:
                                prog_text = (prog.get('title', '') + " " + prog.get('desc', '')).upper()
                                if any(len(t) > 3 and t in prog_text for t in teams):
                                    found_ch = prog
                                    break
                        
                        if found_ch:
                            final_selection.append({
                                "title": event.get('name'),
                                "sid": STREAM_MAP.get(found_ch.get('ch'), "184813"),
                                "start": found_ch.get('start').replace(" ", "")[:14],
                                "stop": found_ch.get('stop').replace(" ", "")[:14],
                                "priority": 100 if "CANADIENS" in name or "BLUE JAYS" in name else 10
                            })
                except: continue

        # 4. RÉGIE ET DISTRIBUTION SUR 5 CANAUX
        final_selection.sort(key=lambda x: x['priority'], reverse=True)
        channels = {i: [] for i in range(1, 6)}
        
        for m in final_selection:
            for i in range(1, 6):
                collision = any(not (m['stop'] <= ex['start'] or m['start'] >= ex['stop']) for ex in channels[i])
                if not collision:
                    channels[i].append(m)
                    break

        # 5. GÉNÉRATION XML
        self.send_response(200)
        self.send_header('Content-type', 'application/xml; charset=utf-8')
        self.end_headers()
        
        xml = '<?xml version="1.0" encoding="UTF-8"?><tv>'
        for i in range(1, 6):
            xml += f'<channel id="CHOIX.{i}"><display-name>CHOIX {i}</display-name></channel>'
            for p in channels[i]:
                # Nettoyage rapide pour le XML
                t = p['title'].replace('&', '&amp;')
                xml += f'<programme start="{p["start"]} +0000" stop="{p["stop"]} +0000" channel="CHOIX.{i}">'
                xml += f'<title lang="fr">{t}</title></programme>'
        xml += '</tv>'
        self.wfile.write(xml.encode('utf-8'))
        
