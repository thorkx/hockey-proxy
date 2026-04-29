from http.server import BaseHTTPRequestHandler
import requests
import json
import time
from datetime import datetime, timedelta

# CONFIGURATION
BIBLE_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

# DURÉES PAR SPORT (en minutes)
SPORT_DURATIONS = {
    "hockey": 165,    # 2h45
    "baseball": 180,  # 3h
    "basketball": 150,# 2h30
    "soccer": 120,    # 2h
    "f1": 135         # 2h15
}

CH_NAMES = {
    "I123.15676.schedulesdirect.org": "RDS", "I124.15677.schedulesdirect.org": "RDS 2",
    "I154.58314.schedulesdirect.org": "TVA Sports", "I155.58315.schedulesdirect.org": "TVA Sports 2",
    "I111.15670.schedulesdirect.org": "TSN 1", "I112.15671.schedulesdirect.org": "TSN 2"
}

def get_match_score(name):
    n = name.upper()
    if "CANADIENS" in n or "MONTREAL" in n: return 1000
    if "BLUE JAYS" in n: return 800
    if "F1" in n or "GRAND PRIX" in n: return 750
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
            bible = requests.get(f"{BIBLE_URL}?t={int(time.time())}", timeout=10).json()
        except: bible = []

        now_utc = datetime.utcnow()
        events_to_stack = []
        seen_matches = set()
        
        # Liste des sports à surveiller
        leagues = [
            ("hockey", "nhl"), 
            ("baseball", "mlb"), 
            ("basketball", "nba"), 
            ("soccer", "usa.1"),
            ("soccer", "eng.1")
        ]
        
        for day in range(3):
            d_str = (now_utc + timedelta(days=day)).strftime("%Y%m%d")
            for sport, league in leagues:
                try:
                    res = requests.get(f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard?dates={d_str}", timeout=5).json()
                    for ev in res.get('events', []):
                        ev_name = ev.get('name', '').upper()
                        if ev_name in seen_matches: continue
                        
                        # --- DÉTERMINATION DE LA DURÉE ---
                        duration_mins = SPORT_DURATIONS.get(sport, 150) # 2h30 par défaut
                        espn_start_dt = datetime.strptime(ev.get('date'), "%Y-%m-%dT%H:%MZ")
                        espn_stop_dt = espn_start_dt + timedelta(minutes=duration_mins)
                        
                        # CONCORDANCE BIBLE
                        keywords = [t for t in ev_name.replace(' AT ',' ').replace(' @ ',' ').split(' ') if len(t) > 4]
                        confirmed_on_ch = None
                        
                        for p in bible:
                            p_start_dt = datetime.strptime(p['start'].split(' ')[0][:14], "%Y%m%d%H%M%S")
                            if abs((espn_start_dt - p_start_dt).total_seconds()) < 14400: # Fenêtre 4h
                                if any(k in p['title'].upper() or k in p['desc'].upper() for k in keywords):
                                    confirmed_on_ch = CH_NAMES.get(p['ch'], "TV")
                                    break
                        
                        if confirmed_on_ch:
                            events_to_stack.append({
                                "title": ev_name,
                                "score": get_match_score(ev_name),
                                "start": espn_start_dt.strftime("%Y%m%d%H%M%S"),
                                "stop": espn_stop_dt.strftime("%Y%m%d%H%M%S"),
                                "ch_name": confirmed_on_ch
                            })
                            seen_matches.add(ev_name)
                except: continue

        # --- ALGORITHME D'EMPILAGE ---
        events_to_stack.sort(key=lambda x: x['score'], reverse=True)
        channels = {i: [] for i in range(1, 6)}
        
        for ev in events_to_stack:
            for i in range(1, 6):
                collision = False
                for existing in channels[i]:
                    if not (ev['stop'] <= existing['start'] or ev['start'] >= existing['stop']):
                        collision = True
                        break
                if not collision:
                    channels[i].append(ev)
                    break

        # --- GÉNÉRATION XML ---
        self.send_response(200)
        self.send_header('Content-type', 'application/xml; charset=utf-8')
        self.end_headers()
        
        xml = '<?xml version="1.0" encoding="UTF-8"?><tv>'
        for i in range(1, 6):
            xml += f'<channel id="CHOIX.{i}"><display-name>CHOIX {i}</display-name></channel>'
            progs = sorted(channels[i], key=lambda x: x['start'])
            cursor = (now_utc - timedelta(hours=6)).strftime("%Y%m%d%H%M%S")
            
            for p in progs:
                if p['start'] > cursor:
                    xml += f'<programme start="{cursor} +0000" stop="{p["start"]} +0000" channel="CHOIX.{i}"><title>Prochainement: {p["title"]}</title></programme>'
                
                xml += f'<programme start="{p["start"]} +0000" stop="{p["stop"]} +0000" channel="CHOIX.{i}">'
                xml += f'<title>{p["title"]} [{p["ch_name"]}]</title></programme>'
                cursor = p['stop']
            
            end = (now_utc + timedelta(days=2)).strftime("%Y%m%d%H%M%S")
            if cursor < end:
                xml += f'<programme start="{cursor} +0000" stop="{end} +0000" channel="CHOIX.{i}"><title>🌙 Fin des événements</title></programme>'

        self.wfile.write((xml + '</tv>').encode('utf-8'))

    def generate_m3u(self):
        host = self.headers.get('Host')
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        m3u = f"#EXTM3U\n"
        for i in range(1, 6):
            m3u += f'#EXTINF:-1 tvg-id="CHOIX.{i}" group-title="REGIE",CHOIX {i}\nhttp://{host}/api/stream/{i}\n'
        self.wfile.write(m3u.encode('utf-8'))
