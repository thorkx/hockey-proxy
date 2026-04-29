from http.server import BaseHTTPRequestHandler
import requests
import json
import time
import re
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

# --- CONFIGURATION ---
BIBLE_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

# -[span_1](start_span)-- BASE DE DONNÉES DE TOUS TES POSTES[span_1](end_span) ---
CH_DATABASE = {
    # QUÉBEC
    "I1000.49609.schedulesdirect.org": {"name": "RDS", "id": "184813", "country": "CA", "lang": "FR"},
    "RDS": {"name": "RDS", "id": "184813", "country": "CA", "lang": "FR"},
    "RDS2": {"name": "RDS2", "id": "184814", "country": "CA", "lang": "FR"},
    "RDSInfo": {"name": "RDSInfo", "id": "184815", "country": "CA", "lang": "FR"},
    "I428.49882.gracenote.com": {"name": "TVASports", "id": "184811", "country": "CA", "lang": "FR"},
    "TVASports": {"name": "TVASports", "id": "184811", "country": "CA", "lang": "FR"},
    "TVASports2": {"name": "TVASports2", "id": "184812", "country": "CA", "lang": "EN"},
    
    # CANADA EN
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

    # UK
    "SkySportF1": {"name": "SkySportF1", "id": "74316", "country": "UK", "lang": "EN"},
    "SkySportMainEvent": {"name": "SkySportMainEvent", "id": "74322", "country": "UK", "lang": "EN"},
    "SkySportPremierLeague": {"name": "SkySportPremierLeague", "id": "74322", "country": "UK", "lang": "EN"},
    "TNTSports1": {"name": "TNTSports1", "id": "74357", "country": "UK", "lang": "EN"},
    "TNTSports2": {"name": "TNTSports2", "id": "74360", "country": "UK", "lang": "EN"},
    "TNTSports3": {"name": "TNTSports3", "id": "74363", "country": "UK", "lang": "EN"},
    "TNTSports4": {"name": "TNTSports4", "id": "75365", "country": "UK", "lang": "EN"},

    # FRANCE
    "Canal+": {"name": "Canal+", "id": "49943", "country": "FRA", "lang": "FR"},
    "Canal+ Sport": {"name": "Canal+ Sport", "id": "49951", "country": "FRA", "lang": "FR"},
    "BeInSports1": {"name": "BeInSports1", "id": "49895", "country": "FRA", "lang": "FR"},
    "BeInSports2": {"name": "BeInSports2", "id": "49896", "country": "FRA", "lang": "FR"},
    "BeInSports3": {"name": "BeInSports3", "id": "49897", "country": "FRA", "lang": "FR"},
    "Eurosport 1": {"name": "Eurosport 1", "id": "50009", "country": "FRA", "lang": "FR"},
    "Eurosport 2": {"name": "Eurosport 2", "id": "50010", "country": "FRA", "lang": "FR"}
}

# On ajoute dynamiquement les IDs que tu as reçus dans ton XML pour qu'ils soient reconnus
CH_DATABASE["I409.68858.schedulesdirect.org"] = {"name": "TSN/SN (Auto)", "id": "71234", "country": "CA", "lang": "EN"}

RULES = [
    ({"league": "nhl", "keywords": ["CANADIENS", "MONTREAL", "HABS"]}, 1000),
    ({"league": "usa.1", "keywords": ["CF MONTREAL", "MONTREAL"]}, 900),
    ({"league": "mlb", "keywords": ["BLUE JAYS", "TORONTO"]}, 800),
    ({"league": "nba", "keywords": ["RAPTORS"]}, 700),
    ({"league": "nhl", "keywords": []}, 500)
]

def clean_text(text):
    """Enlève accents et caractères spéciaux pour faciliter la comparaison"""
    text = text.upper()
    return re.sub(r'[ÉÈÊË]', 'E', re.sub(r'[ÀÂÄ]', 'A', text))

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
        for day in range(2):
            d_str = (now_utc + timedelta(days=day)).strftime("%Y%m%d")
            for sport, league in leagues:
                urls.append((f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard?dates={d_str}", league))

        events_to_stack = []
        seen_matches = set()
        
        with ThreadPoolExecutor(max_workers=8) as executor:
            future_to_url = {executor.submit(fetch_espn, url): lg for url, lg in urls}
            for future in future_to_url:
                league = future_to_url[future]
                data = future.result()
                for ev in data.get('events', []):
                    ev_name = ev['name'].upper()
                    if ev_name in seen_matches: continue
                    
                    start_dt = datetime.strptime(ev['date'], "%Y-%m-%dT%H:%MZ")
                    ch_key = ""
                    # On cherche les noms d'équipes (ex: ["CANADIENS", "LIGHTNING"])
                    kw_list = [k for k in ev_name.replace('@',' ').replace('AT',' ').split() if len(k) > 3]
                    
                    for p in bible:
                        p_title = clean_text(p['title'])
                        # Si l'une des équipes ESPN est dans le titre EPG
                        if any(k in p_title for k in kw_list):
                            p_start = datetime.strptime(p['start'].split(' ')[0][:14], "%Y%m%d%H%M%S")
                            if abs((start_dt - p_start).total_seconds()) < 14400: # 4h
                                ch_key = p['ch']
                                break
                    
                    score = 0
                    for criteria, s in RULES:
                        if criteria["league"] == league:
                            if not criteria["keywords"] or any(k in ev_name for k in criteria["keywords"]):
                                score = s
                                break
                    
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
            try:
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
            except:
                self.send_response(302)
                self.send_header('Location', f"{STREAM_BASE}/184813")
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
        
