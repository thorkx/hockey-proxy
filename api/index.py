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

# --- MAPPAGE DE LA BIBLE (FR + EN) ---
CH_DATABASE = {
    # FR - CANADA
    "I1000.49609.schedulesdirect.org": {"name": "RDS", "id": "184813", "lang": "FR"},
    "I123.15676.schedulesdirect.org": {"name": "RDS", "id": "184813", "lang": "FR"},
    "I124.15677.schedulesdirect.org": {"name": "RDS 2", "id": "184814", "lang": "FR"},
    "I1881.73275.schedulesdirect.org": {"name": "RDS 2", "id": "184814", "lang": "FR"},
    "I428.49882.gracenote.com": {"name": "TVA Sports", "id": "184811", "lang": "FR"},
    "I154.58314.schedulesdirect.org": {"name": "TVA Sports", "id": "184811", "lang": "FR"},
    "I193.73142.schedulesdirect.org": {"name": "TVA Sports", "id": "184811", "lang": "FR"},
    "I155.58315.schedulesdirect.org": {"name": "TVA Sports 2", "id": "184812", "lang": "FR"},
    
    # EN - CANADA (Priorité Sportsnet/TSN)
    "I405.62111.schedulesdirect.org": {"name": "Sportsnet 4K", "id": "157674", "lang": "EN"},
    "I409.68858.schedulesdirect.org": {"name": "TSN / Sportsnet", "id": "71234", "lang": "EN"},
    "SNEast": {"name": "Sportsnet East", "id": "71518", "lang": "EN"},
    "SNWest": {"name": "Sportsnet West", "id": "71521", "lang": "EN"},
    "SNPacific": {"name": "Sportsnet Pacific", "id": "71520", "lang": "EN"},
    "SNOntario": {"name": "Sportsnet Ontario", "id": "71519", "lang": "EN"},
    "SNOne": {"name": "Sportsnet One", "id": "157675", "lang": "EN"},
    "SN360": {"name": "Sportsnet 360", "id": "71517", "lang": "EN"},
    "TSN1": {"name": "TSN 1", "id": "71234", "lang": "EN"},
    "TSN2": {"name": "TSN 2", "id": "71235", "lang": "EN"},
    "TSN3": {"name": "TSN 3", "id": "71236", "lang": "EN"},
    "TSN4": {"name": "TSN 4", "id": "71237", "lang": "EN"},
    "TSN5": {"name": "TSN 5", "id": "71238", "lang": "EN"},
    
    # EUROPE / AUTRES
    "CanalPlus.fr": {"name": "Canal+", "id": "49943", "lang": "FR"},
    "beINSPORTSMAX4.fr": {"name": "beIN MAX 4", "id": "49898", "lang": "FR"},
    "Sky_Sports_F1": {"name": "Sky F1", "id": "74316", "lang": "EN"}
}

def clean_text(t):
    if not t: return ""
    t = re.sub(r'[ÉÈÊË]', 'E', t.upper())
    t = re.sub(r'[ÀÂÄ]', 'A', t)
    return re.sub(r'[^\w\s]', ' ', t)

def find_match_in_bible(ev_name, bible_data, ev_date_str):
    ev_time = datetime.strptime(ev_date_str, "%Y-%m-%dT%H:%MZ")
    teams = [w for w in clean_text(ev_name).split() if len(w) > 3 and w not in ["MONTREAL", "TORONTO", "BOSTON"]]
    
    for prog in bible_data:
        try:
            p_start = datetime.strptime(prog['start'].split(' ')[0], "%Y%m%d%H%M%S")
            if abs((ev_time - p_start).total_seconds()) < 14400: # 4h window
                search_zone = clean_text(prog.get('title', '')) + " " + clean_text(prog.get('desc', ''))
                if any(team in search_zone for team in teams):
                    return prog['ch']
        except: continue
    return None

def fetch_espn(url):
    try: return requests.get(url, timeout=3).json()
    except: return {}

class handler(BaseHTTPRequestHandler):
    def get_organized_events(self):
        try: bible = requests.get(BIBLE_URL, timeout=5).json()
        except: bible = []
        
        now = datetime.utcnow()
        events = []
        seen = set()
        leagues = [("hockey","nhl"), ("basketball","nba"), ("baseball","mlb"), ("soccer","usa.1")]
        
        urls = []
        for day in range(2):
            ds = (now + timedelta(days=day)).strftime("%Y%m%d")
            for sp, lg in leagues:
                urls.append((f"https://site.api.espn.com/apis/site/v2/sports/{sp}/{lg}/scoreboard?dates={ds}", lg))

        with ThreadPoolExecutor(max_workers=8) as exe:
            futures = {exe.submit(fetch_espn, u): lg for u, lg in urls}
            for f in futures:
                lg = futures[f]
                for ev in f.result().get('events', []):
                    name = ev['name'].upper()
                    if name in seen: continue
                    
                    ch_key = find_match_in_bible(name, bible, ev['date'])
                    start_t = datetime.strptime(ev['date'], "%Y-%m-%dT%H:%MZ")
                    
                    # --- SYSTÈME DE SCORING ---
                    score = 0
                    if lg == "nhl": score = 500
                    elif lg == "nba": score = 400
                    else: score = 300

                    if any(k in name for k in ["CANADIENS", "RAPTORS", "BLUE JAYS", "CF MONTREAL"]):
                        score += 1000
                    
                    info = CH_DATABASE.get(ch_key, {})
                    ch_name = info.get("name", "").upper()

                    # Priorité Sportsnet/TSN sur TVA
                    if "SPORTSNET" in ch_name or "TSN" in ch_name:
                        score += 400
                    if info.get("lang") == "FR":
                        score += 100
                    if "TVA" in ch_name or "TVA" in str(ch_key).upper():
                        score -= 800 

                    events.append({
                        "title": name, "score": score, "start": start_t, 
                        "stop": start_t + timedelta(hours=3), "ch_key": ch_key
                    })
                    seen.add(name)

        events.sort(key=lambda x: x['score'], reverse=True)
        chans = {i: [] for i in range(1, 6)}
        for e in events:
            for i in range(1, 6):
                if not any(not (e['stop'] <= ex['start'] or e['start'] >= ex['stop']) for ex in chans[i]):
                    chans[i].append(e); break
        return chans

    def do_GET(self):
        if "/stream/" in self.path:
            try:
                idx = int(self.path.split('/')[-1])
                chans = self.get_organized_events()
                now = datetime.utcnow()
                sid = "184813" # RDS Fallback
                for m in chans.get(idx, []):
                    if m['start'] <= now <= m['stop']:
                        sid = CH_DATABASE.get(m['ch_key'], {}).get("id", "184813")
                        break
                self.send_response(302); self.send_header('Location', f"{STREAM_BASE}/{sid}"); self.end_headers()
            except:
                self.send_response(302); self.send_header('Location', f"{STREAM_BASE}/184813"); self.end_headers()
        elif self.path.endswith('.m3u'):
            self.send_response(200); self.send_header('Content-type', 'text/plain'); self.end_headers()
            host = self.headers.get('Host')
            m3u = "#EXTM3U\n" + "\n".join([f'#EXTINF:-1 tvg-id="CHOIX.{i}",CHOIX {i}\nhttp://{host}/api/stream/{i}' for i in range(1,6)])
            self.wfile.write(m3u.encode('utf-8'))
        else:
            self.generate_xml_output()

    def generate_xml_output(self):
        chans = self.get_organized_events()
        now = datetime.utcnow()
        self.send_response(200); self.send_header('Content-type', 'application/xml; charset=utf-8'); self.end_headers()
        xml = '<?xml version="1.0" encoding="UTF-8"?><tv>'
        for i in range(1, 6):
            xml += f'<channel id="CHOIX.{i}"><display-name>CHOIX {i}</display-name></channel>'
            cursor = now - timedelta(hours=6)
            for p in sorted(chans[i], key=lambda x: x['start']):
                st, en = p['start'].strftime("%Y%m%d%H%M%S"), p['stop'].strftime("%Y%m%d%H%M%S")
                info = CH_DATABASE.get(p['ch_key'], {})
                ch_n = info.get('name', p['ch_key'] if p['ch_key'] else "À CONFIRMER")
                lang = info.get('lang', "??")
                title = f"{p['title']} ({lang}) | {ch_n}"
                if p['start'] > cursor:
                    xml += f'<programme start="{cursor.strftime("%Y%m%d%H%M%S")} +0000" stop="{st} +0000" channel="CHOIX.{i}"><title>➡️ Suivant: {title}</title></programme>'
                xml += f'<programme start="{st} +0000" stop="{en} +0000" channel="CHOIX.{i}"><title>{title}</title><desc>Source: {ch_n} ({lang})</desc></programme>'
                cursor = p['stop']
        self.wfile.write((xml + '</tv>').encode('utf-8'))
        
