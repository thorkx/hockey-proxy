from http.server import BaseHTTPRequestHandler
import requests
import json
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

# --- CONFIGURATION ---
BIBLE_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

# --- BASE DE DONNÉES COMPLÈTE (UK INCLUS) ---
CH_DATABASE = {
    "I1000.49609.schedulesdirect.org": {"name": "RDS", "id": "184813", "country": "CA", "lang": "FR"},
    "I123.15676.schedulesdirect.org": {"name": "RDS", "id": "184813", "country": "CA", "lang": "FR"},
    "I124.15677.schedulesdirect.org": {"name": "RDS 2", "id": "184814", "country": "CA", "lang": "FR"},
    "I428.49882.gracenote.com": {"name": "TVA Sports", "id": "184811", "country": "CA", "lang": "FR"},
    "I154.58314.schedulesdirect.org": {"name": "TVA Sports", "id": "184811", "country": "CA", "lang": "FR"},
    "I155.58315.schedulesdirect.org": {"name": "TVA Sports 2", "id": "184812", "country": "CA", "lang": "FR"},
    "I405.62111.schedulesdirect.org": {"name": "Sportsnet (4K)", "id": "157674", "country": "CA", "lang": "EN"},
    "SNEast": {"name": "SNEast", "id": "71518", "country": "CA", "lang": "EN"},
    "SNWest": {"name": "SNWest", "id": "71521", "country": "CA", "lang": "EN"},
    "SNPacific": {"name": "SNPacific", "id": "71520", "country": "CA", "lang": "EN"},
    "SNOntario": {"name": "SNOntario", "id": "71519", "country": "CA", "lang": "EN"},
    "SNOne": {"name": "SNOne", "id": "157675", "country": "CA", "lang": "EN"},
    "SN360": {"name": "SN360", "id": "71517", "country": "CA", "lang": "EN"},
    "SNWorld": {"name": "SNWorld", "id": "71526", "country": "CA", "lang": "EN"},
    "TSN1": {"name": "TSN1", "id": "71234", "country": "CA", "lang": "EN"},
    "TSN2": {"name": "TSN2", "id": "71235", "country": "CA", "lang": "EN"},
    "TSN3": {"name": "TSN3", "id": "71236", "country": "CA", "lang": "EN"},
    "TSN4": {"name": "TSN4", "id": "71237", "country": "CA", "lang": "EN"},
    "TSN5": {"name": "TSN5", "id": "71238", "country": "CA", "lang": "EN"},
    "OneSoccer": {"name": "OneSoccer", "id": "19320", "country": "CA", "lang": "EN"},
    "CanalPlus.fr": {"name": "Canal+", "id": "49943", "country": "FRA", "lang": "FR"},
    "CanalPlusSport.fr": {"name": "Canal+ Sport", "id": "49951", "country": "FRA", "lang": "FR"},
    "BeINSports1.fr": {"name": "beIN Sports 1", "id": "49895", "country": "FRA", "lang": "FR"},
    "BeINSports2.fr": {"name": "beIN Sports 2", "id": "49896", "country": "FRA", "lang": "FR"},
    "BeINSports3.fr": {"name": "beIN Sports 3", "id": "49897", "country": "FRA", "lang": "FR"},
    "RMCSport1.fr": {"name": "RMC Sport 1", "id": "50145", "country": "FRA", "lang": "FR"},
    "Eurosport1.fr": {"name": "Eurosport 1", "id": "49987", "country": "FRA", "lang": "FR"},
    "Eurosport2.fr": {"name": "Eurosport 2", "id": "49988", "country": "FRA", "lang": "FR"},
    "TNT_Sports_1": {"name": "TNT Sports 1", "id": "71151", "country": "UK", "lang": "EN"},
    "TNT_Sports_2": {"name": "TNT Sports 2", "id": "71152", "country": "UK", "lang": "EN"},
    "TNT_Sports_3": {"name": "TNT Sports 3", "id": "71153", "country": "UK", "lang": "EN"},
    "TNT_Sports_4": {"name": "TNT Sports 4", "id": "71154", "country": "UK", "lang": "EN"},
    "Sky_Sports_Main_Event": {"name": "Sky Sports Main Event", "id": "74310", "country": "UK", "lang": "EN"},
    "Sky_Sports_Premier_League": {"name": "Sky Sports Premier League", "id": "74311", "country": "UK", "lang": "EN"},
    "Sky_Sports_Football": {"name": "Sky Sports Football", "id": "74312", "country": "UK", "lang": "EN"},
    "Sky_Sports_F1": {"name": "Sky Sports F1", "id": "74316", "country": "UK", "lang": "EN"},
    "ESPN": {"name": "ESPN", "id": "18345", "country": "US", "lang": "EN"},
    "FoxSports1": {"name": "FoxSports1", "id": "18242", "country": "US", "lang": "EN"}
}

RULES = [
    ({"league": "nhl", "keywords": ["CANADIENS", "MONTREAL", "HABS"]}, 1000),
    ({"league": "usa.1", "keywords": ["CF MONTREAL", "MONTREAL"]}, 900),
    ({"league": "mlb", "keywords": ["BLUE JAYS", "TORONTO"]}, 800),
    ({"league": "nba", "keywords": ["RAPTORS"]}, 700),
    ({"league": "nhl", "keywords": ["MAPLE LEAFS"]}, -500),
    ({"league": "nhl", "keywords": []}, 500),
    ({"league": "mlb", "keywords": []}, 300),
    ({"league": "usa.1", "keywords": []}, 150)
]

def fetch_espn(url):
    try: return requests.get(url, timeout=3).json()
    except: return {}

class handler(BaseHTTPRequestHandler):
    def get_organized_events(self):
        try: bible = requests.get(BIBLE_URL, timeout=5).json()
        except: bible = []

        now_utc = datetime.utcnow()
        urls = []
        leagues = [("hockey", "nhl"), ("baseball", "mlb"), ("basketball", "nba"), ("soccer", "usa.1")]
        
        # On réduit à 2 jours (Auj/Demain) pour la vitesse
        for day in range(2):
            d_str = (now_utc + timedelta(days=day)).strftime("%Y%m%d")
            for sport, league in leagues:
                urls.append((f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard?dates={d_str}", league))

        # REQUÊTES EN PARALLÈLE (Gain de temps énorme)
        events_to_stack = []
        seen_matches = set()
        with ThreadPoolExecutor(max_workers=8) as executor:
            future_to_url = {executor.submit(fetch_espn, url): league for url, league in urls}
            for future in future_to_url:
                league = future_to_url[future]
                data = future.result()
                for ev in data.get('events', []):
                    ev_name = ev['name'].upper()
                    if ev_name in seen_matches: continue
                    
                    start_dt = datetime.strptime(ev['date'], "%Y-%m-%dT%H:%MZ")
                    ch_key = ""
                    kw = [t for t in ev_name.replace(' AT ',' ').replace(' @ ',' ').split(' ') if len(t) >= 3]
                    
                    for p in bible:
                        p_start = datetime.strptime(p['start'].split(' ')[0][:14], "%Y%m%d%H%M%S")
                        if abs((start_dt - p_start).total_seconds()) < 10800: # 3h window
                            if any(k in p['title'].upper() for k in kw):
                                ch_key = p['ch']
                                break
                    
                    score = 0
                    match_found = False
                    for criteria, s in RULES:
                        if criteria["league"] == league:
                            if criteria["keywords"]:
                                if any(k in ev_name for k in criteria["keywords"]): 
                                    score = s; match_found = True; break
                            elif not match_found: score = s; match_found = True
                    
                    info = CH_DATABASE.get(ch_key, {})
                    if info.get("lang") == "FR": score += 200
                    if info.get("country") == "CA": score += 100
                    if "TVA" in ch_key.upper() or "TVA" in info.get("name","").upper(): score -= 1000

                    events_to_stack.append({
                        "title": ev_name, "score": score, "start": start_dt, 
                        "stop": start_dt + timedelta(minutes=180), "ch_key": ch_key
                    })
                    seen_matches.add(ev_name)

        events_to_stack.sort(key=lambda x: x['score'], reverse=True)
        channels = {i: [] for i in range(1, 6)}
        for ev in events_to_stack:
            for i in range(1, 6):
                if not any(not (ev['stop'] <= ex['start'] or ev['start'] >= ex['stop']) for ex in channels[i]):
                    channels[i].append(ev); break
        return channels

    def do_GET(self):
        if "/stream/" in self.path:
            idx = int(self.path.split('/')[-1])
            chans = self.get_organized_events()
            now = datetime.utcnow()
            sid = "184813"
            for m in chans.get(idx, []):
                if m['start'] <= now <= m['stop']:
                    sid = CH_DATABASE.get(m['ch_key'], {}).get("id", "184813")
                    break
            self.send_response(302)
            self.send_header('Location', f"{STREAM_BASE}/{sid}")
            self.end_headers()
        elif self.path.endswith('.m3u'):
            host = self.headers.get('Host')
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            m3u = "#EXTM3U\n" + "\n".join([f'#EXTINF:-1 tvg-id="CHOIX.{i}",CHOIX {i}\nhttp://{host}/api/stream/{i}' for i in range(1,6)])
            self.wfile.write(m3u.encode('utf-8'))
        else:
            self.generate_xml_output()

    def generate_xml_output(self):
        chans = self.get_organized_events()
        now = datetime.utcnow()
        self.send_response(200)
        self.send_header('Content-type', 'application/xml; charset=utf-8')
        self.end_headers()
        xml = '<?xml version="1.0" encoding="UTF-8"?><tv>'
        for i in range(1, 6):
            xml += f'<channel id="CHOIX.{i}"><display-name>CHOIX {i}</display-name></channel>'
            cursor = (now - timedelta(hours=6))
            for p in sorted(chans[i], key=lambda x: x['start']):
                info = CH_DATABASE.get(p['ch_key'], {})
                ch_n = info.get('name', p['ch_key'] if p['ch_key'] else "À CONFIRMER")
                title = f"{p['title']} | Source: {ch_n}"
                if p['start'] > cursor:
                    xml += f'<programme start="{cursor.strftime("%Y%m%d%H%M%S")} +0000" stop="{p["start"].strftime("%Y%m%d%H%M%S")} +0000" channel="CHOIX.{i}"><title>➡️ Suivant: {title}</title></programme>'
                xml += f'<programme start="{p["start"].strftime("%Y%m%d%H%M%S")} +0000" stop="{p["stop"].strftime("%Y%m%d%H%M%S")} +0000" channel="CHOIX.{i}"><title>{title}</title><desc>Source: {ch_n} ({info.get("lang","??")}/{info.get("country","??")})</desc></programme>'
                cursor = p['stop']
        self.wfile.write((xml + '</tv>').encode('utf-8'))
        
