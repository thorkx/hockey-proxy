from http.server import BaseHTTPRequestHandler
import requests
import json
import time
from datetime import datetime, timedelta

# --- CONFIGURATION DES SOURCES ---
BIBLE_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

# --- BASE DE DONNÉES DES CHAÎNES (Mappage Complet : Bible ID -> Stream ID) ---
CH_DATABASE = {
    # QUÉBEC / CANADA (FR)
    "I1000.49609.schedulesdirect.org": {"name": "RDS", "id": "184813", "country": "CA", "lang": "FR"},
    "I123.15676.schedulesdirect.org": {"name": "RDS", "id": "184813", "country": "CA", "lang": "FR"},
    "I124.15677.schedulesdirect.org": {"name": "RDS 2", "id": "184814", "country": "CA", "lang": "FR"},
    "ID_RDS_INFO": {"name": "RDS Info", "id": "184815", "country": "CA", "lang": "FR"},
    "I428.49882.gracenote.com": {"name": "TVA Sports", "id": "184811", "country": "CA", "lang": "FR"},
    "I154.58314.schedulesdirect.org": {"name": "TVA Sports", "id": "184811", "country": "CA", "lang": "FR"},
    "I155.58315.schedulesdirect.org": {"name": "TVA Sports 2", "id": "184812", "country": "CA", "lang": "FR"},
    
    # CANADA (EN) - SPORTSNET & TSN
    "I405.62111.schedulesdirect.org": {"name": "Sportsnet (4K)", "id": "157674", "country": "CA", "lang": "EN"},
    "SNOne": {"name": "SNOne", "id": "157675", "country": "CA", "lang": "EN"},
    "SN360": {"name": "SN360", "id": "71517", "country": "CA", "lang": "EN"},
    "SNEast": {"name": "SNEast", "id": "71518", "country": "CA", "lang": "EN"},
    "SNOntario": {"name": "SNOntario", "id": "71519", "country": "CA", "lang": "EN"},
    "SNWest": {"name": "SNWest", "id": "71521", "country": "CA", "lang": "EN"},
    "SNPacific": {"name": "SNPacific", "id": "71520", "country": "CA", "lang": "EN"},
    "SNWorld": {"name": "SNWorld", "id": "71526", "country": "CA", "lang": "EN"},
    "TSN1": {"name": "TSN1", "id": "71234", "country": "CA", "lang": "EN"},
    "TSN2": {"name": "TSN2", "id": "71235", "country": "CA", "lang": "EN"},
    "TSN3": {"name": "TSN3", "id": "71236", "country": "CA", "lang": "EN"},
    "TSN4": {"name": "TSN4", "id": "71237", "country": "CA", "lang": "EN"},
    "TSN5": {"name": "TSN5", "id": "71238", "country": "CA", "lang": "EN"},
    "OneSoccer": {"name": "OneSoccer", "id": "19320", "country": "CA", "lang": "EN"},

    # FRANCE (Racacax)
    "CanalPlus.fr": {"name": "Canal+", "id": "49943", "country": "FRA", "lang": "FR"},
    "CanalPlusSport.fr": {"name": "Canal+ Sport", "id": "49951", "country": "FRA", "lang": "FR"},
    "BeINSports1.fr": {"name": "beIN Sports 1", "id": "49895", "country": "FRA", "lang": "FR"},
    "BeINSports2.fr": {"name": "beIN Sports 2", "id": "49896", "country": "FRA", "lang": "FR"},
    "BeINSports3.fr": {"name": "beIN Sports 3", "id": "49897", "country": "FRA", "lang": "FR"},
    "RMCSport1.fr": {"name": "RMC Sport 1", "id": "50145", "country": "FRA", "lang": "FR"},
    "Eurosport1.fr": {"name": "Eurosport 1", "id": "49987", "country": "FRA", "lang": "FR"},
    "Eurosport2.fr": {"name": "Eurosport 2", "id": "49988", "country": "FRA", "lang": "FR"},

    # UK (TNT & SKY)
    "TNT_Sports_1": {"name": "TNT Sports 1", "id": "71151", "country": "UK", "lang": "EN"},
    "TNT_Sports_2": {"name": "TNT Sports 2", "id": "71152", "country": "UK", "lang": "EN"},
    "TNT_Sports_3": {"name": "TNT Sports 3", "id": "71153", "country": "UK", "lang": "EN"},
    "TNT_Sports_4": {"name": "TNT Sports 4", "id": "71154", "country": "UK", "lang": "EN"},
    "Sky_Sports_Main_Event": {"name": "Sky Sports Main Event", "id": "74310", "country": "UK", "lang": "EN"},
    "Sky_Sports_Premier_League": {"name": "Sky Sports Premier League", "id": "74311", "country": "UK", "lang": "EN"},
    "Sky_Sports_Football": {"name": "Sky Sports Football", "id": "74312", "country": "UK", "lang": "EN"},
    "Sky_Sports_Cricket": {"name": "Sky Sports Cricket", "id": "74313", "country": "UK", "lang": "EN"},
    "Sky_Sports_Golf": {"name": "Sky Sports Golf", "id": "74314", "country": "UK", "lang": "EN"},
    "Sky_Sports_F1": {"name": "Sky Sports F1", "id": "74316", "country": "UK", "lang": "EN"},
    "Sky_Sports_Action": {"name": "Sky Sports Action", "id": "74315", "country": "UK", "lang": "EN"},
    "Sky_Sports_Arena": {"name": "Sky Sports Arena", "id": "74317", "country": "UK", "lang": "EN"},

    # USA
    "ESPN": {"name": "ESPN", "id": "18345", "country": "US", "lang": "EN"},
    "ESPN2": {"name": "ESPN2", "id": "18346", "country": "US", "lang": "EN"},
    "ESPNDeportes": {"name": "ESPN Deportes", "id": "18356", "country": "US", "lang": "ES"},
    "BeInSports_US": {"name": "BeInSports", "id": "71320", "country": "US", "lang": "EN"},
    "BeInSports_USA": {"name": "BeInSports USA", "id": "18312", "country": "US", "lang": "EN"},
    "BeInSports_Xtra": {"name": "BeInSports Xtra", "id": "19489", "country": "US", "lang": "EN"},
    "CBS_Sports": {"name": "CBS Sports", "id": "18335", "country": "US", "lang": "EN"},
    "FoxSports1": {"name": "FoxSports1", "id": "18242", "country": "US", "lang": "EN"}
}

# --- ALGORITHME DE SCORE ---
RULES = [
    ({"league": "nhl", "keywords": ["CANADIENS", "MONTREAL", "HABS"]}, 1000),
    ({"league": "usa.1", "keywords": ["CF MONTREAL", "MONTREAL"]}, 900), # Corrigé Impact -> CF Montréal
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
    if "TVA" in ch_key.upper() or "TVA" in info.get("name", "").upper():
        score -= 1000 # Malus TVA Sports
    return score

class handler(BaseHTTPRequestHandler):
    def get_organized_events(self):
        try:
            bible = requests.get(f"{BIBLE_URL}?t={int(time.time())}", timeout=10).json()
        except: bible = []

        now_utc = datetime.utcnow()
        events_to_stack = []
        seen_matches = set()
        leagues = [("hockey", "nhl"), ("baseball", "mlb"), ("basketball", "nba"), ("soccer", "usa.1")]
        
        for day in range(3):
            d_str = (now_utc + timedelta(days=day)).strftime("%Y%m%d")
            for sport, league in leagues:
                try:
                    res = requests.get(f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard?dates={d_str}", timeout=5).json()
                    for ev in res.get('events', []):
                        ev_name = ev['name'].upper()
                        if ev_name in seen_matches: continue
                        start_dt = datetime.strptime(ev['date'], "%Y-%m-%dT%H:%MZ")
                        stop_dt = start_dt + timedelta(minutes=180)
                        
                        ch_key = ""
                        keywords = [t for t in ev_name.replace(' AT ',' ').replace(' @ ',' ').split(' ') if len(t) >= 3]
                        
                        for p in bible:
                            p_start = datetime.strptime(p['start'].split(' ')[0][:14], "%Y%m%d%H%M%S")
                            if abs((start_dt - p_start).total_seconds()) < 14400:
                                if any(k in p['title'].upper() for k in keywords):
                                    ch_key = p['ch']
                                    break
                        
                        events_to_stack.append({
                            "title": ev_name,
                            "score": calculate_score(ev_name, league, ch_key),
                            "start": start_dt,
                            "stop": stop_dt,
                            "ch_key": ch_key
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
                final_id = "184813" # Fallback RDS
                for match in channels.get(choix_idx, []):
                    if match['start'] <= now <= match['stop']:
                        final_id = CH_DATABASE.get(match['ch_key'], {}).get("id", "184813")
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
                ch_name = info.get('name', p['ch_key'] if p['ch_key'] else "À CONFIRMER")
                
                if p['start'] > cursor:
                    xml += f'<programme start="{cursor.strftime("%Y%m%d%H%M%S")} +0000" stop="{s_str} +0000" channel="CHOIX.{i}"><title>➡️ Suivant: {p["title"]} | Source: {ch_name}</title></programme>'
                
                xml += f'<programme start="{s_str} +0000" stop="{e_str} +0000" channel="CHOIX.{i}">'
                xml += f'<title>{p["title"]} | Source: {ch_name}</title>'
                xml += f'<desc>Source: {ch_name} ({info.get("lang","??")}/{info.get("country","??")}).</desc>'
                xml += f'</programme>'
                cursor = p['stop']
        self.wfile.write((xml + '</tv>').encode('utf-8'))
        
