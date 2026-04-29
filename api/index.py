from http.server import BaseHTTPRequestHandler
import requests
import json
from datetime import datetime, timedelta

# CONFIGURATION
BIBLE_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

STREAM_MAP = {
    "I123.15676.schedulesdirect.org": "71151", "I124.15677.schedulesdirect.org": "71152",
    "I154.58314.schedulesdirect.org": "71165", "I155.58315.schedulesdirect.org": "71166",
    "I410.18802.schedulesdirect.org": "71236", "I409.18801.schedulesdirect.org": "71234",
    "I408.18800.schedulesdirect.org": "71237", "I411.18803.schedulesdirect.org": "71235",
    "I412.18804.schedulesdirect.org": "71233", "I413.18805.schedulesdirect.org": "71232",
    "I111.15670.schedulesdirect.org": "71243", "I112.15671.schedulesdirect.org": "71244",
    "I113.15672.schedulesdirect.org": "71245", "I114.15673.schedulesdirect.org": "71246",
    "I115.15674.schedulesdirect.org": "71247", "I446.52300.schedulesdirect.org": "71239"
}

CH_NAMES = {
    "I123.15676.schedulesdirect.org": "RDS", "I124.15677.schedulesdirect.org": "RDS 2",
    "I154.58314.schedulesdirect.org": "TVA Sports", "I155.58315.schedulesdirect.org": "TVA Sports 2",
    "I111.15670.schedulesdirect.org": "TSN 1", "I112.15671.schedulesdirect.org": "TSN 2",
    "I113.15672.schedulesdirect.org": "TSN 3", "I114.15673.schedulesdirect.org": "TSN 4",
    "I115.15674.schedulesdirect.org": "TSN 5"
}

def get_match_score(name):
    n = name.upper()
    if any(k in n for k in ["CANADIENS", "MONTREAL", "HABS"]): return 1000
    if "CF MONTREAL" in n: return 900
    if "BLUE JAYS" in n: return 800
    return 100

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if "/stream/" in self.path:
            self.send_response(302)
            self.send_header('Location', f"{STREAM_BASE}/71151")
            self.end_headers()
        elif self.path.endswith('.m3u'):
            self.generate_m3u()
        else:
            self.generate_xml()

    def generate_xml(self):
        try:
            # On force le no-cache pour être sûr d'avoir les dernières modifs
            bible = requests.get(BIBLE_URL, headers={'Cache-Control': 'no-cache'}, timeout=10).json()
        except: bible = []

        now_utc = datetime.utcnow()
        events_found = []
        
        # On élargit les ligues pour être sûr d'avoir du contenu
        leagues = [("hockey","nhl"), ("baseball","mlb"), ("soccer","usa.1"), ("soccer","eng.1"), ("basketball","nba")]
        
        for day in range(3):
            d_str = (now_utc + timedelta(days=day)).strftime("%Y%m%d")
            for sport, league in leagues:
                try:
                    res = requests.get(f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard?dates={d_str}", timeout=5).json()
                    for ev in res.get('events', []):
                        ev_name = ev.get('name', '')
                        ev_time_str = ev.get('date')
                        ev_time = datetime.strptime(ev_time_str, "%Y-%m-%dT%H:%MZ")
                        
                        # Matcher avec la bible
                        best_prog = None
                        teams = [t for t in ev_name.upper().replace(' AT ',' ').replace(' @ ',' ').split(' ') if len(t) > 3]
                        
                        for p in bible:
                            p_start = datetime.strptime(p['start'].split(' ')[0][:14], "%Y%m%d%H%M%S")
                            # Si le match ESPN et l'EPG sont à moins de 3h d'intervalle
                            if abs((ev_time - p_start).total_seconds()) < 10800:
                                if any(t in p['title'].upper() for t in teams):
                                    best_prog = p
                                    break
                        
                        if best_prog:
                            events_found.append({
                                "title": ev_name,
                                "score": get_match_score(ev_name),
                                "start": best_prog['start'].split(' ')[0][:14],
                                "stop": best_prog['stop'].split(' ')[0][:14],
                                "ch_display": CH_NAMES.get(best_prog['ch'], "TV")
                            })
                except: continue

        # Attribution
        events_found.sort(key=lambda x: x['score'], reverse=True)
        channels = {i: [] for i in range(1, 6)}
        
        for ev in events_found:
            for i in range(1, 6):
                collision = False
                for existing in channels[i]:
                    if not (ev['stop'] <= existing['start'] or ev['start'] >= existing['stop']):
                        collision = True
                        break
                if not collision:
                    channels[i].append(ev)
                    break

        # Génération XML
        self.send_response(200)
        self.send_header('Content-type', 'application/xml; charset=utf-8')
        self.end_headers()
        
        xml = '<?xml version="1.0" encoding="UTF-8"?><tv>'
        for i in range(1, 6):
            xml += f'<channel id="CHOIX.{i}"><display-name>CHOIX {i}</display-name></channel>'
            
            # On trie et on remplit les trous avec un curseur qui commence loin derrière
            progs = sorted(channels[i], key=lambda x: x['start'])
            cursor = (now_utc - timedelta(hours=12)).strftime("%Y%m%d%H%M%S")
            
            for p in progs:
                if p['start'] > cursor:
                    xml += f'<programme start="{cursor} +0000" stop="{p["start"]} +0000" channel="CHOIX.{i}"><title>☕ EN ATTENTE : {p["title"].replace("&", "&amp;")}</title></programme>'
                
                xml += f'<programme start="{p["start"]} +0000" stop="{p["stop"]} +0000" channel="CHOIX.{i}"><title>{p["title"].replace("&", "&amp;")} [{p["ch_display"]}]</title></programme>'
                cursor = p['stop']
            
            # Bloc de fin
            end_cursor = (now_utc + timedelta(days=2)).strftime("%Y%m%d%H%M%S")
            if cursor < end_cursor:
                xml += f'<programme start="{cursor} +0000" stop="{end_cursor} +0000" channel="CHOIX.{i}"><title>🌙 FIN DES ÉVÉNEMENTS</title></programme>'

        self.wfile.write((xml + '</tv>').encode('utf-8'))

    def generate_m3u(self):
        host = self.headers.get('Host')
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        m3u = "#EXTM3U\n"
        for i in range(1, 6):
            m3u += f'#EXTINF:-1 tvg-id="CHOIX.{i}" group-title="REGIE",CHOIX {i}\nhttp://{host}/api/stream/{i}\n'
        self.wfile.write(m3u.encode('utf-8'))
        
