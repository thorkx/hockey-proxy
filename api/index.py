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
    ("basketball", "nba")
]

# SIDs par défaut
DEFAULT_SID = "184813" # RDS
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
                        espn_time = datetime.strptime(event.get('date'), "%Y-%m-%dT%H:%MZ")
                        
                        # --- TENTATIVE DE MATCHING AVEC LA BIBLE ---
                        found_ch = None
                        teams = name.replace(' AT ', ' ').replace(' @ ', ' ').split(' ')
                        clean_teams = [t for t in teams if len(t) > 3]

                        for prog in bible:
                            try:
                                p_start = datetime.strptime(prog.get('start', '')[:14], "%Y%m%d%H%M%S")
                                if abs((espn_time - p_start).total_seconds()) / 3600 <= 2.0:
                                    if any(t in prog.get('title', '').upper() or t in prog.get('desc', '').upper() for t in clean_teams):
                                        found_ch = prog
                                        break
                            except: continue

                        # --- CONSTRUCTION DE L'ITEM (HYBRIDE) ---
                        if found_ch:
                            # On a l'info complète
                            sid = STREAM_MAP.get(found_ch.get('ch'), DEFAULT_SID)
                            start = found_ch.get('start')[:14]
                            stop = found_ch.get('stop')[:14]
                            title = f"LIVE: {event.get('name')}"
                        else:
                            # Mode PRÉVISIONNEL (Pas dans la bible encore)
                            sid = DEFAULT_SID
                            start = espn_time.strftime("%Y%m%d%H%M%S")
                            stop = (espn_time + timedelta(hours=3)).strftime("%Y%m%d%H%M%S")
                            title = f"PRÉVU: {event.get('name')} (Canal à confirmer)"

                        final_selection.append({
                            "title": title,
                            "sid": sid,
                            "start": start,
                            "stop": stop,
                            "priority": 100 if any(f in name for f in ["CANADIENS", "JAYS", "CITY", "MTL"]) else 10
                        })
                except: continue

        # Tri et Distribution sur 5 canaux
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
        
