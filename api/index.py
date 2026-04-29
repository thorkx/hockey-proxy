from http.server import BaseHTTPRequestHandler
import requests
import json
import re
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

# --- CONFIGURATION ---
BIBLE_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

# --- LOGOS DES LIGUES ---
LOGOS = {
    "nhl": "https://a.espncdn.com/i/teamlogos/leagues/500/nhl.png",
    "mlb": "https://a.espncdn.com/i/teamlogos/leagues/500/mlb.png",
    "nba": "https://a.espncdn.com/i/teamlogos/leagues/500/nba.png",
    "usa.1": "https://a.espncdn.com/i/teamlogos/leagues/500/mls.png",
    "default": "https://a.espncdn.com/i/espn/misc_logos/espn_white.png"
}

# --- LISTE DES IDS PRIORITAIRES (Sportsnet & TSN) ---
PRIORITY_IDS = [
    "I405.62111.schedulesdirect.org", "I409.68858.schedulesdirect.org", 
    "SNEast", "SNWest", "SNPacific", "SNOntario", "SNOne", "SN360",
    "TSN1", "TSN2", "TSN3", "TSN4", "TSN5"
]

# --- MAPPAGE COMPLET ---
CH_DATABASE = {
    "I405.62111.schedulesdirect.org": {"name": "Sportsnet 4K", "id": "157674", "lang": "EN"},
    "I409.68858.schedulesdirect.org": {"name": "TSN/SN (EPG)", "id": "71234", "lang": "EN"},
    "I1000.49609.schedulesdirect.org": {"name": "RDS", "id": "184813", "lang": "FR"},
    "I123.15676.schedulesdirect.org": {"name": "RDS", "id": "184813", "lang": "FR"},
    "I193.73142.schedulesdirect.org": {"name": "TVA Sports", "id": "184811", "lang": "FR"},
    "I154.58314.schedulesdirect.org": {"name": "TVA Sports", "id": "184811", "lang": "FR"},
    "SNEast": {"name": "SN East", "id": "71518", "lang": "EN"},
    "TSN1": {"name": "TSN 1", "id": "71234", "lang": "EN"}
}

def clean_name(t):
    if not t: return ""
    t = t.upper()
    t = re.sub(r'HOCKEY|LNH|NBA|BASKETBALL|BASEBALL|MLB| AT | VS |CONTRE', ' ', t)
    t = re.sub(r'[ÉÈÊË]', 'E', t)
    t = re.sub(r'[ÀÂÄ]', 'A', t)
    return re.sub(r'[^\w\s]', ' ', t)

def find_match_in_bible(ev_name, bible_data, ev_date_str):
    ev_time = datetime.strptime(ev_date_str, "%Y-%m-%dT%H:%MZ")
    keywords = [w for w in clean_name(ev_name).split() if len(w) > 3 and w not in ["MONTREAL", "TORONTO"]]
    
    matches = []
    for prog in bible_data:
        try:
            p_start = datetime.strptime(prog['start'].split(' ')[0], "%Y%m%d%H%M%S")
            if abs((ev_time - p_start).total_seconds()) < 14400:
                full_text = clean_name(prog.get('title', '')) + " " + clean_name(prog.get('desc', ''))
                if any(kw in full_text for kw in keywords):
                    matches.append(prog['ch'])
        except: continue
    
    if matches:
        for m in matches:
            if m in PRIORITY_IDS: return m
        return matches[0]
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
        
        leagues_list = [("hockey","nhl"), ("basketball","nba"), ("baseball","mlb"), ("soccer","usa.1")]
        urls = []
        for day in range(2):
            ds = (now + timedelta(days=day)).strftime("%Y%m%d")
            for sp, lg in leagues_list:
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
                    
                    score = 100
                    if lg == "nhl": score += 500
                    if any(k in name for k in ["CANADIENS", "RAPTORS", "BLUE JAYS"]): score += 1000
                    
                    if ch_key in PRIORITY_IDS: score += 500
                    if ch_key and ("TVA" in ch_key.upper() or "184811" in str(ch_key)):
                        score -= 600

                    events.append({
                        "title": name, "score": score, "start": start_t, 
                        "stop": start_t + timedelta(hours=3), "ch_key": ch_key,
                        "league": lg
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
            idx = int(self.path.split('/')[-1])
            chans = self.get_organized_events()
            now = datetime.utcnow()
            sid = "184813"
            for m in chans.get(idx, []):
                if m['start'] <= now <= m['stop']:
                    sid = CH_DATABASE.get(m['ch_key'], {}).get("id", "184813")
                    break
            self.send_response(302); self.send_header('Location', f"{STREAM_BASE}/{sid}"); self.end_headers()
        elif self.path.endswith('.m3u'):
            self.send_response(200); self.send_header('Content-type', 'text/plain'); self.end_headers()
            host = self.headers.get('Host')
            m3u = "#EXTM3U\n"
            for i in range(1,6):
                logo = LOGOS.get("default")
                m3u += f'#EXTINF:-1 tvg-id="CHOIX.{i}" tvg-logo="{logo}",CHOIX {i}\nhttp://{host}/api/stream/{i}\n'
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
                logo_url = LOGOS.get(p['league'], LOGOS['default'])
                
                title = f"{p['title']} ({lang}) | {ch_n}"
                if p['start'] > cursor:
                    xml += f'<programme start="{cursor.strftime("%Y%m%d%H%M%S")} +0000" stop="{st} +0000" channel="CHOIX.{i}"><title>➡️ Suivant: {title}</title></programme>'
                
                xml += f'<programme start="{st} +0000" stop="{en} +0000" channel="CHOIX.{i}">'
                xml += f'<title>{title}</title>'
                xml += f'<desc>Source: {ch_n}</desc>'
                xml += f'<icon src="{logo_url}" />'
                xml += '</programme>'
                cursor = p['stop']
        self.wfile.write((xml + '</tv>').encode('utf-8'))
        
