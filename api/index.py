from http.server import BaseHTTPRequestHandler
import requests
import json
from datetime import datetime, timedelta

# CONFIGURATION
BIBLE_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

LEAGUES = [
    ("hockey", "nhl"),
    ("baseball", "mlb"),
    ("soccer", "eng.1"),
    ("soccer", "fra.1"),
    ("basketball", "nba") # Ajouté pour remplir
]

STREAM_MAP = {
    "I408.18800.schedulesdirect.org": "71520",
    "I123.15676.schedulesdirect.org": "184813",
    "I111.15670.schedulesdirect.org": "184816",
    "I154.58314.schedulesdirect.org": "184821"
}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            bible = requests.get(BIBLE_URL, timeout=10).json()
        except:
            bible = []

        final_selection = []
        now_utc = datetime.utcnow()

        for day_offset in range(4):
            target_date = (now_utc + timedelta(days=day_offset)).strftime("%Y%m%d")
            
            for sport, league in LEAGUES:
                url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard?dates={target_date}"
                try:
                    res = requests.get(url, timeout=5).json()
                    for event in res.get('events', []):
                        name = event.get('name', '').upper()
                        # ESPN Date: 2026-04-29T23:00Z -> Objet Datetime
                        espn_time = datetime.strptime(event.get('date'), "%Y-%m-%dT%H:%MZ")
                        
                        found_ch = None
                        teams = name.replace(' AT ', ' ').replace(' @ ', ' ').split(' ')
                        # On ne garde que les noms significatifs (ex: "Canadiens", pas "at")
                        clean_teams = [t for t in teams if len(t) > 3]

                        for prog in bible:
                            # Parse le start du bot (format: 20260429030000)
                            try:
                                prog_start_str = prog.get('start', '').replace(" ", "")[:14]
                                prog_time = datetime.strptime(prog_start_str, "%Y%m%d%H%M%S")
                            except: continue

                            # FLEXIBILITÉ : On accepte si le match commence à +/- 2 heures de l'heure ESPN
                            diff = abs((espn_time - prog_time).total_seconds()) / 3600
                            
                            if diff <= 2.0:
                                prog_text = (prog.get('title', '') + " " + prog.get('desc', '')).upper()
                                if any(t in prog_text for t in clean_teams):
                                    found_ch = prog
                                    break
                        
                        if found_ch:
                            final_selection.append({
                                "title": event.get('name'),
                                "sid": STREAM_MAP.get(found_ch.get('ch'), "184813"),
                                "start": found_ch.get('start').replace(" ", "")[:14],
                                "stop": found_ch.get('stop').replace(" ", "")[:14],
                                "priority": 100 if any(fav in name for fav in ["CANADIENS", "JAYS", "CITY"]) else 10
                            })
                except: continue

        # Tri et Distribution (Inchangé)
        final_selection.sort(key=lambda x: x['priority'], reverse=True)
        channels = {i: [] for i in range(1, 6)}
        for m in final_selection:
            for i in range(1, 6):
                collision = any(not (m['stop'] <= ex['start'] or m['start'] >= ex['stop']) for ex in channels[i])
                if not collision:
                    channels[i].append(m)
                    break

        # Génération XML
        self.send_response(200)
        self.send_header('Content-type', 'application/xml; charset=utf-8')
        self.end_headers()
        xml = '<?xml version="1.0" encoding="UTF-8"?><tv>'
        for i in range(1, 6):
            xml += f'<channel id="CHOIX.{i}"><display-name>CHOIX {i}</display-name></channel>'
            for p in channels[i]:
                t = p['title'].replace('&', '&amp;')
                xml += f'<programme start="{p["start"]} +0000" stop="{p["stop"]} +0000" channel="CHOIX.{i}">'
                xml += f'<title lang="fr">{t}</title></programme>'
        xml += '</tv>'
        self.wfile.write(xml.encode('utf-8'))
        
