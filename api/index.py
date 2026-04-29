from http.server import BaseHTTPRequestHandler
import requests
import json
import time
from datetime import datetime, timedelta

# --- CONFIGURATION DES PRIORITÉS ---
RULES = [
    ({"league": "nhl", "keywords": ["CANADIENS", "MONTREAL", "HABS"]}, 1000),
    ({"league": "usa.1", "keywords": ["MONTREAL", "IMPACT"]}, 900),
    ({"league": "mlb", "keywords": ["BLUE JAYS", "TORONTO"]}, 800),
    ({"league": "nba", "keywords": ["RAPTORS"]}, 700),
    ({"league": "nhl", "keywords": ["MAPLE LEAFS", "TORONTO"]}, -500),
    ({"league": "nhl", "keywords": []}, 500),
    ({"league": "mlb", "keywords": []}, 300),
    ({"league": "nba", "keywords": []}, 200),
    ({"league": "usa.1", "keywords": []}, 150)
]

SPORT_DATA = {
    "hockey": {"min": 165, "icon": "🏒"},
    "baseball": {"min": 180, "icon": "⚾"},
    "basketball": {"min": 150, "icon": "🏀"},
    "soccer": {"min": 120, "icon": "⚽"},
    "f1": {"min": 135, "icon": "🏎️"}
}

BIBLE_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

# VERIFIE BIEN QUE CES IDS SONT EXACTEMENT LES MÊMES DANS TON JSON
CH_NAMES = {
    "I123.15676.schedulesdirect.org": "RDS", 
    "I124.15677.schedulesdirect.org": "RDS 2",
    "I154.58314.schedulesdirect.org": "TVA Sports", 
    "I155.58315.schedulesdirect.org": "TVA Sports 2",
    "I111.15670.schedulesdirect.org": "TSN 1",
    "I112.15671.schedulesdirect.org": "TSN 2",
    "I113.15672.schedulesdirect.org": "TSN 3",
    "I114.15673.schedulesdirect.org": "TSN 4",
    "I115.15674.schedulesdirect.org": "TSN 5"
}

def calculate_score(ev_name, league_key):
    name = ev_name.upper()
    final_score = 0
    match_found = False
    for criteria, score in RULES:
        if criteria["league"] == league_key:
            if criteria["keywords"]:
                if any(k in name for k in criteria["keywords"]): return score
            else:
                if not match_found:
                    final_score = score
                    match_found = True
    return final_score

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
        
        leagues_to_track = [("hockey", "nhl"), ("baseball", "mlb"), ("basketball", "nba"), ("soccer", "usa.1")]
        
        for day in range(4):
            d_str = (now_utc + timedelta(days=day)).strftime("%Y%m%d")
            for sport, league in leagues_to_track:
                try:
                    res = requests.get(f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard?dates={d_str}", timeout=5).json()
                    for ev in res.get('events', []):
                        ev_name = ev.get('name', '').upper()
                        if ev_name in seen_matches: continue
                        
                        start_dt = datetime.strptime(ev.get('date'), "%Y-%m-%dT%H:%MZ")
                        s_info = SPORT_DATA.get(sport, {"min": 150, "icon": "📺"})
                        stop_dt = start_dt + timedelta(minutes=s_info["min"])
                        
                        espn_keywords = [t for t in ev_name.replace(' AT ',' ').replace(' @ ',' ').split(' ') if len(t) >= 3]
                        
                        # --- DETERMINATION DE LA CHAINE ---
                        display_ch = "À CONFIRMER"
                        for p in bible:
                            p_title = p['title'].upper()
                            p_start = datetime.strptime(p['start'].split(' ')[0][:14], "%Y%m%d%H%M%S")
                            
                            if abs((start_dt - p_start).total_seconds()) < 14400:
                                if any(k in p_title for k in espn_keywords) or \
                                   (("MONTREAL" in ev_name or "CANADIENS" in ev_name) and ("HOCKEY" in p_title or "CANADIENS" in p_title)):
                                    
                                    # Correction ici : on cherche l'ID dans CH_NAMES
                                    raw_ch_id = p.get('ch', '')
                                    display_ch = CH_NAMES.get(raw_ch_id, raw_ch_id if raw_ch_id else "SOURCE")
                                    break
                        
                        events_to_stack.append({
                            "title": ev_name,
                            "score": calculate_score(ev_name, league),
                            "start": start_dt.strftime("%Y%m%d%H%M%S"),
                            "stop": stop_dt.strftime("%Y%m%d%H%M%S"),
                            "ch_name": display_ch,
                            "icon": s_info["icon"]
                        })
                        seen_matches.add(ev_name)
                except: continue

        events_to_stack.sort(key=lambda x: x['score'], reverse=True)
        channels = {i: [] for i in range(1, 6)}
        for ev in events_to_stack:
            for i in range(1, 6):
                collision = False
                for existing in channels[i]:
                    if not (ev['stop'] <= existing['start'] or ev['start'] >= existing['stop']):
                        collision = True; break
                if not collision:
                    channels[i].append(ev); break

        self.send_response(200)
        self.send_header('Content-type', 'application/xml; charset=utf-8')
        self.end_headers()
        
        xml = '<?xml version="1.0" encoding="UTF-8"?><tv>'
        for i in range(1, 6):
            xml += f'<channel id="CHOIX.{i}"><display-name>CHOIX {i}</display-name></channel>'
            progs = sorted(channels[i], key=lambda x: x['start'])
            cursor = (now_utc - timedelta(hours=6)).strftime("%Y%m%d%H%M%S")
            for p in progs:
                icon = p.get('icon', '📺')
                source = p.get('ch_name', 'À CONFIRMER')
                full_title = f"{p['title']} [{source}]"
                
                if p['start'] > cursor:
                    xml += f'<programme start="{cursor} +0000" stop="{p["start"]} +0000" channel="CHOIX.{i}"><title>➡️{icon} Prochainement: {full_title}</title></programme>'
                
                xml += f'<programme start="{p["start"]} +0000" stop="{p["stop"]} +0000" channel="CHOIX.{i}"><title>{icon} {full_title}</title></programme>'
                cursor = p['stop']
            
            limit = (now_utc + timedelta(days=4)).strftime("%Y%m%d%H%M%S")
            if cursor < limit:
                xml += f'<programme start="{cursor} +0000" stop="{limit} +0000" channel="CHOIX.{i}"><title>🌙 Fin des émissions</title></programme>'
        self.wfile.write((xml + '</tv>').encode('utf-8'))

    def generate_m3u(self):
        host = self.headers.get('Host')
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        m3u = "#EXTM3U\n"
        for i in range(1, 6):
            m3u += f'#EXTINF:-1 tvg-id="CHOIX.{i}",CHOIX {i}\nhttp://{host}/api/stream/{i}\n'
        self.wfile.write(m3u.encode('utf-8'))
        
