from http.server import BaseHTTPRequestHandler
import requests
import json
from datetime import datetime, timedelta

# CONFIGURATION
BIBLE_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

LEAGUES = {
    "hockey": "🏒",
    "baseball": "⚾",
    "soccer": "⚽",
    "basketball": "🏀"
}

# Pour l'affichage propre dans le titre
CH_NAMES = {
    "I408.18800.schedulesdirect.org": "SN West",
    "I123.15676.schedulesdirect.org": "RDS",
    "I111.15670.schedulesdirect.org": "TSN",
    "I154.58314.schedulesdirect.org": "TVA Sports",
    "I446.52300.schedulesdirect.org": "Sky MX"
}

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
            
            for sport, icon in LEAGUES.items():
                league_id = "nhl" if sport == "hockey" else "mlb" if sport == "baseball" else "eng.1" if sport == "soccer" else "nba"
                url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league_id}/scoreboard?dates={target_date}"
                
                try:
                    res = requests.get(url, timeout=5).json()
                    for event in res.get('events', []):
                        name = event.get('name', '').upper()
                        espn_time = datetime.strptime(event.get('date'), "%Y-%m-%dT%H:%MZ")
                        
                        # --- MATCHMAKING & RECHERCHE DE MULTI-DIFFUSION ---
                        matching_progs = []
                        teams = name.replace(' AT ', ' ').replace(' @ ', ' ').split(' ')
                        clean_teams = [t for t in teams if len(t) > 3]

                        for prog in bible:
                            try:
                                p_start = datetime.strptime(prog.get('start', '')[:14], "%Y%m%d%H%M%S")
                                if abs((espn_time - p_start).total_seconds()) / 3600 <= 2.0:
                                    prog_text = (prog.get('title', '') + " " + prog.get('desc', '')).upper()
                                    if any(t in prog_text for t in clean_teams):
                                        matching_progs.append(prog)
                            except: continue

                        # --- CONSTRUCTION DU TITRE ENRICHI ---
                        if matching_progs:
                            # Canal utilisé pour le stream (le premier trouvé qui est dans notre STREAM_MAP)
                            primary = next((p for p in matching_progs if p['ch'] in STREAM_MAP), matching_progs[0])
                            sid = STREAM_MAP.get(primary['ch'], "184813")
                            
                            # Liste de tous les canaux qui diffusent
                            all_channels = [CH_NAMES.get(p['ch'], p['name']) for p in matching_progs]
                            ch_info = f"[{' | '.join(all_channels)}]"
                            
                            title = f"{icon} {event.get('name')} {ch_info}"
                            start, stop = primary['start'][:14], primary['stop'][:14]
                        else:
                            # Mode PRÉVU
                            sid = "184813"
                            start = espn_time.strftime("%Y%m%d%H%M%S")
                            stop = (espn_time + timedelta(hours=3)).strftime("%Y%m%d%H%M%S")
                            title = f"{icon} {event.get('name')} [À CONFIRMER]"

                        final_selection.append({
                            "title": title,
                            "sid": sid,
                            "start": start,
                            "stop": stop,
                            "priority": 100 if any(f in name for f in ["CANADIENS", "JAYS", "MTL"]) else 10
                        })
                except: continue

        # Tri et Distribution
        final_selection.sort(key=lambda x: x['priority'], reverse=True)
        channels = {i: [] for i in range(1, 6)}
        for m in final_selection:
            for i in range(1, 6):
                collision = any(not (m['stop'] <= ex['start'] or m['start'] >= ex['stop']) for ex in channels[i])
                if not collision:
                    channels[i].append(m)
                    break

        # Sortie XML
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
        self.wfile.write((xml + '</tv>').encode('utf-8'))
        
