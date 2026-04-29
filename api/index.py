from http.server import BaseHTTPRequestHandler
import requests
import json
from datetime import datetime, timedelta

# CONFIGURATION
BIBLE_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
ESPN_NHL = "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard"
ESPN_MLB = "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

# Tes SIDs prioritaires
STREAM_MAP = {
    "I408.18800.schedulesdirect.org": "71520",
    "I123.15676.schedulesdirect.org": "184813",
    "I111.15670.schedulesdirect.org": "184816",
    "I154.58314.schedulesdirect.org": "184821"
}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 1. RÉCUPÉRER LA BIBLE (EPG DU BOT)
        try:
            bible = requests.get(BIBLE_URL, timeout=5).json()
        except:
            bible = []

        # 2. RÉCUPÉRER LES MATCHS DEPUIS ESPN
        espn_events = []
        for url in [ESPN_NHL, ESPN_MLB]:
            try:
                res = requests.get(url, timeout=5).json()
                espn_events.extend(res.get('events', []))
            except: continue

        # 3. MATCHING CHIRURGICAL
        final_selection = []
        for event in espn_events:
            name = event.get('name', '').upper() # Ex: "Montreal Canadiens at Boston Bruins"
            short_name = event.get('shortName', '').upper() # Ex: "MTL @ BOS"
            
            # Heure ESPN est en ISO UTC (ex: 2026-04-29T23:00Z)
            # On simplifie pour matcher le format 20260429...
            date_str = event.get('date', '').replace('-', '').replace(':', '').replace('T', '')[:12]

            # On cherche dans la bible un programme qui contient une des équipes à la même heure
            found_stream = None
            for prog in bible:
                prog_title = prog.get('title', '').upper()
                prog_desc = prog.get('desc', '').upper()
                
                # Si le nom de l'équipe est dans le titre ou la desc de la bible
                # On vérifie aussi si l'heure concorde (à 1h près)
                if any(team in prog_title or team in prog_desc for team in name.split(' ')):
                    if prog.get('start', '')[:10] == date_str[:10]: # Même jour
                        found_stream = prog
                        break
            
            if found_stream:
                final_selection.append({
                    "title": event.get('name'),
                    "sid": STREAM_MAP.get(found_stream.get('ch'), "184813"),
                    "start": found_stream.get('start', '').replace(" ", "")[:14],
                    "stop": found_stream.get('stop', '').replace(" ", "")[:14],
                    "priority": 100 if "CANADIENS" in name or "BLUE JAYS" in name else 10
                })

        # 4. DISTRIBUTION SUR 5 CANAUX
        final_selection.sort(key=lambda x: x['priority'], reverse=True)
        channels = {i: [] for i in range(1, 6)}
        for m in final_selection:
            for i in range(1, 6):
                collision = any(not (m['stop'] <= ex['start'] or m['start'] >= ex['stop']) for ex in channels[i])
                if not collision:
                    channels[i].append(m)
                    break

        # 5. GÉNÉRATION XMLTV
        self.send_response(200)
        self.send_header('Content-type', 'application/xml; charset=utf-8')
        self.end_headers()
        
        xml = '<?xml version="1.0" encoding="UTF-8"?><tv>'
        for i in range(1, 6):
            xml += f'<channel id="CHOIX.{i}"><display-name>CHOIX {i}</display-name></channel>'
            for p in channels[i]:
                xml += f'<programme start="{p["start"]} +0000" stop="{p["stop"]} +0000" channel="CHOIX.{i}">'
                xml += f'<title lang="fr">{p["title"]}</title></programme>'
        xml += '</tv>'
        self.wfile.write(xml.encode('utf-8'))
        
