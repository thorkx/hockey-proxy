from http.server import BaseHTTPRequestHandler
import requests
import json
import time
from datetime import datetime, timedelta

# --- CONFIGURATION ---
BIBLE_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

CH_DATABASE = {
    "RDS": {"id": "184813", "country": "CA", "lang": "FR"},
    "RDS2": {"id": "184814", "country": "CA", "lang": "FR"},
    "RDSInfo": {"id": "184815", "country": "CA", "lang": "FR"},
    "TVASports": {"id": "184811", "country": "CA", "lang": "FR"},
    "TVASports2": {"id": "184812", "country": "CA", "lang": "FR"},
    "Sportsnet (4K)": {"id": "157674", "country": "CA", "lang": "EN"},
    "SNOne": {"id": "157675", "country": "CA", "lang": "EN"},
    "SN360": {"id": "71517", "country": "CA", "lang": "EN"},
    "SNEast": {"id": "71518", "country": "CA", "lang": "EN"},
    "SNOntario": {"id": "71519", "country": "CA", "lang": "EN"},
    "SNWest": {"id": "71521", "country": "CA", "lang": "EN"},
    "SNPacific": {"id": "71520", "country": "CA", "lang": "EN"},
    "SNWorld": {"id": "71526", "country": "CA", "lang": "EN"},
    "TSN1": {"id": "71234", "country": "CA", "lang": "EN"},
    "TSN2": {"id": "71235", "country": "CA", "lang": "EN"},
    "TSN3": {"id": "71236", "country": "CA", "lang": "EN"},
    "TSN4": {"id": "71237", "country": "CA", "lang": "EN"},
    "TSN5": {"id": "71238", "country": "CA", "lang": "EN"},
    "OneSoccer": {"id": "19320", "country": "CA", "lang": "EN"},
    "ESPN": {"id": "18345", "country": "US", "lang": "EN"},
    "ESPN2": {"id": "18346", "country": "US", "lang": "EN"},
    "ESPNDeportes": {"id": "18356", "country": "US", "lang": "ES"},
    "BeInSports": {"id": "71320", "country": "US", "lang": "EN"},
    "BeInSports USA": {"id": "18312", "country": "US", "lang": "EN"},
    "BeInSports Xtra": {"id": "19489", "country": "US", "lang": "EN"},
    "CBS Sports": {"id": "18335", "country": "US", "lang": "EN"},
    "FoxSports1": {"id": "18242", "country": "US", "lang": "EN"},
    "CanalPlus.fr": {"id": "49943", "country": "FRA", "lang": "FR"},
    "CanalPlusSport.fr": {"id": "49951", "country": "FRA", "lang": "FR"},
    "BeINSports1.fr": {"id": "49895", "country": "FRA", "lang": "FR"},
    "BeINSports2.fr": {"id": "49896", "country": "FRA", "lang": "FR"},
    "RMCSport1.fr": {"id": "50145", "country": "FRA", "lang": "FR"}
}

RULES = [
    ({"league": "nhl", "keywords": ["CANADIENS", "MONTREAL", "HABS"]}, 1000),
    ({"league": "usa.1", "keywords": ["MONTREAL", "IMPACT", "CF MONTREAL"]}, 900),
    ({"league": "mlb", "keywords": ["BLUE JAYS", "TORONTO"]}, 800),
    ({"league": "nba", "keywords": ["RAPTORS"]}, 700),
    ({"league": "nhl", "keywords": ["MAPLE LEAFS", "TORONTO"]}, -500),
    ({"league": "nhl", "keywords": []}, 500),
    ({"league": "mlb", "keywords": []}, 300),
    ({"league": "nba", "keywords": []}, 200),
    ({"league": "usa.1", "keywords": []}, 150)
]

def calculate_score(ev_name, league_key, ch_key):
    name = ev_name.upper()
    score = 0
    match_found = False
    for criteria, s in RULES:
        if criteria["league"] == league_key:
            if criteria["keywords"]:
                if any(k in name for k in criteria["keywords"]): 
                    score = s; match_found = True; break
            elif not match_found:
                score = s; match_found = True
    
    info = CH_DATABASE.get(ch_key, {})
    if info.get("lang") == "FR": score += 200
    if info.get("country") == "CA": score += 100
    if "TVA" in ch_key.upper(): score -= 1000
    return score

class handler(BaseHTTPRequestHandler):
    def get_organized_events(self):
        """ Logique commune pour le guide et la redirection """
        try:
            bible = requests.get(f"{BIBLE_URL}?t={int(time.time())}", timeout=10).json()
        except: bible = []

        now_utc = datetime.utcnow()
        events_to_stack = []
        seen_matches = set()
        leagues = [("hockey", "nhl"), ("baseball", "mlb"), ("basketball", "nba"), ("soccer", "usa.1")]
        
        for day in range(2): # 2 jours suffisent pour la redirection instantanée
            d_str = (now_utc + timedelta(days=day)).strftime("%Y%m%d")
            for sport, league in leagues:
                try:
                    res = requests.get(f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard?dates={d_str}", timeout=5).json()
                    for ev in res.get('events', []):
                        ev_name = ev['name'].upper()
                        if ev_name in seen_matches: continue
                        start_dt = datetime.strptime(ev['date'], "%Y-%m-%dT%H:%MZ")
                        stop_dt = start_dt + timedelta(minutes=180)
                        
                        ch_key, stream_id = "", "184813" # Fallback RDS
                        keywords = [t for t in ev_name.replace(' AT ',' ').replace(' @ ',' ').split(' ') if len(t) >= 3]
                        
                        for p in bible:
                            p_start = datetime.strptime(p['start'].split(' ')[0][:14], "%Y%m%d%H%M%S")
                            if abs((start_dt - p_start).total_seconds()) < 14400:
                                if any(k in p['title'].upper() for k in keywords):
                                    ch_key = p['ch']
                                    stream_id = CH_DATABASE.get(ch_key, {}).get("id", "184813")
                                    break
                        
                        events_to_stack.append({
                            "title": ev_name,
                            "score": calculate_score(ev_name, league, ch_key),
                            "start": start_dt,
                            "stop": stop_dt,
                            "ch_key": ch_key,
                            "stream_id": stream_id
                        })
                        seen_matches.add(ev_name)
                except: continue

        events_to_stack.sort(key=lambda x: x['score'], reverse=True)
        channels = {i: [] for i in range(1, 6)}
        for ev in events_to_stack:
            for i in range(1, 6):
                collision = False
                for ex in channels[i]:
                    if not (ev['stop'] <= ex['start'] or ev['start'] >= ex['stop']):
                        collision = True; break
                if not collision:
                    channels[i].append(ev); break
        return channels

    def do_GET(self):
        if "/stream/" in self.path:
            try:
                choix_idx = int(self.path.split('/')[-1])
                channels = self.get_organized_events()
                now = datetime.utcnow()
                
                # Trouver le stream_id du match qui joue MAINTENANT sur ce CHOIX
                final_id = "184813" # Fallback RDS
                for match in channels.get(choix_idx, []):
                    if match['start'] <= now <= match['stop']:
                        final_id = match['stream_id']
                        break
                
                self.send_response(302)
                self.send_header('Location', f"{STREAM_BASE}/{final_id}")
                self.end_headers()
            except:
                self.send_response(302)
                self.send_header('Location', f"{STREAM_BASE}/184813")
                self.end_headers()

        elif self.path.endswith('.m3u'):
            host = self.headers.get('Host')
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            m3u = "#EXTM3U\n"
            for i in range(1, 6):
                m3u += f'#EXTINF:-1 tvg-id="CHOIX.{i}",CHOIX {i}\nhttp://{host}/api/stream/{i}\n'
            self.wfile.write(m3u.encode('utf-8'))
        else:
            # Code pour générer le XML (similaire à get_organized_events mais formate en XML)
            self.generate_xml_output()

    def generate_xml_output(self):
        channels = self.get_organized_events()
        now_utc = datetime.utcnow()
        self.send_response(200)
        self.send_header('Content-type', 'application/xml; charset=utf-8')
        self.end_headers()
        xml = '<?xml version="1.0" encoding="UTF-8"?><tv>'
        for i in range(1, 6):
            xml += f'<channel id="CHOIX.{i}"><display-name>CHOIX {i}</display-name></channel>'
            cursor = (now_utc - timedelta(hours=6))
            for p in sorted(channels[i], key=lambda x: x['start']):
                s_str = p['start'].strftime("%Y%m%d%H%M%S")
                e_str = p['stop'].strftime("%Y%m%d%H%M%S")
                info = CH_DATABASE.get(p['ch_key'], {})
                label = f"[{info.get('lang','??')}] {p['ch_key']}" if p['ch_key'] else "[À CONFIRMER]"
                
                if p['start'] > cursor:
                    xml += f'<programme start="{cursor.strftime("%Y%m%d%H%M%S")} +0000" stop="{s_str} +0000" channel="CHOIX.{i}"><title>➡️ Prochainement: {p["title"]} {label}</title></programme>'
                
                xml += f'<programme start="{s_str} +0000" stop="{e_str} +0000" channel="CHOIX.{i}"><title>{p["title"]} {label}</title></programme>'
                cursor = p['stop']
        self.wfile.write((xml + '</tv>').encode('utf-8'))
        
