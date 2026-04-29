from http.server import BaseHTTPRequestHandler
import requests
import json
import re
import html
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

# ==========================================
#        CONFIGURATION DES PRIORITÉS
# ==========================================
PRIORITY_CONFIG = {
    "LEAGUES": {
        "nhl": 500, "nba": 400, "eng.1": 350, "fra.1": 350,
        "uefa.champions": 375, "mlb": 300, "usa.1": 250
    },
    "TEAMS": {
        "CANADIENS": 1000, "RAPTORS": 1000, "BLUE JAYS": 1000, 
        "CF MONTREAL": 1000, "WREXHAM": 1200
    },
    "CHANNELS": {
        "BONUS_ENGLISH_PREMIUM": 500, "BONUS_FRENCH": 150, "PENALTY_TVA": -800
    }
}

SPECIAL_TEAMS_SCAN = {
    "WREXHAM": ("soccer", "eng.3") 
}

PREMIUM_IDS = [
    "I405.62111.schedulesdirect.org", "I409.68858.schedulesdirect.org", 
    "SNEast", "SNWest", "SNPacific", "SNOntario", "SNOne", "SN360",
    "TSN1", "TSN2", "TSN3", "TSN4", "TSN5"
]

# ==========================================
#              BASE DE DONNÉES
# ==========================================
BIBLE_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

CH_DATABASE = {
    "I405.62111.schedulesdirect.org": {"name": "Sportsnet 4K", "id": "157674", "lang": "EN"},
    "I409.68858.schedulesdirect.org": {"name": "TSN/SN (EPG)", "id": "71234", "lang": "EN"},
    "I1000.49609.schedulesdirect.org": {"name": "RDS", "id": "184813", "lang": "FR"},
    "I193.73142.schedulesdirect.org": {"name": "TVA Sports", "id": "184811", "lang": "FR"}
}

# On garde SPORT_ICONS pour le titre, mais on n'utilise plus LOGOS pour la balise icon
SPORT_ICONS = {"nhl": "🏒", "nba": "🏀", "mlb": "⚾", "soccer": "⚽", "default": "🏆"}

def escape_xml(text):
    if not text: return ""
    return text.encode('ascii', 'xmlcharrefreplace').decode()

def clean_name(t):
    if not t: return ""
    t = t.upper()
    t = re.sub(r'HOCKEY|LNH|NBA|SOCCER|FOOTBALL| AT | VS |CONTRE', ' ', t)
    t = re.sub(r'[ÉÈÊË]', 'E', t); t = re.sub(r'[ÀÂÄ]', 'A', t)
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
            if m in PREMIUM_IDS: return m
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
        events, seen = [], set()
        
        leagues_to_fetch = [("hockey","nhl"), ("basketball","nba"), ("baseball","mlb"), ("soccer","eng.1"), ("soccer","usa.1")]
        for team_name, league_info in SPECIAL_TEAMS_SCAN.items():
            if league_info not in leagues_to_fetch: leagues_to_fetch.append(league_info)

        urls = []
        for day in range(2):
            ds = (now + timedelta(days=day)).strftime("%Y%m%d")
            for sp, lg in leagues_to_fetch:
                urls.append((f"https://site.api.espn.com/apis/site/v2/sports/{sp}/{lg}/scoreboard?dates={ds}", lg))

        with ThreadPoolExecutor(max_workers=10) as exe:
            futures = {exe.submit(fetch_espn, u): lg for u, lg in urls}
            for f in futures:
                lg = futures[f]
                for ev in f.result().get('events', []):
                    name = ev['name'].upper()
                    if name in seen: continue
                    ch_key = find_match_in_bible(name, bible, ev['date'])
                    score = PRIORITY_CONFIG["LEAGUES"].get(lg, 100)
                    for team, bonus in PRIORITY_CONFIG["TEAMS"].items():
                        if team in name: score += bonus
                    info = CH_DATABASE.get(ch_key, {})
                    if ch_key in PREMIUM_IDS: score += PRIORITY_CONFIG["CHANNELS"]["BONUS_ENGLISH_PREMIUM"]
                    if info.get("lang") == "FR": score += PRIORITY_CONFIG["CHANNELS"]["BONUS_FRENCH"]
                    if ch_key and ("TVA" in str(ch_key).upper() or "184811" in str(ch_key)):
                        score += PRIORITY_CONFIG["CHANNELS"]["PENALTY_TVA"]
                    events.append({
                        "title": name, "score": score, "league": lg,
                        "start": datetime.strptime(ev['date'], "%Y-%m-%dT%H:%MZ"), 
                        "stop": datetime.strptime(ev['date'], "%Y-%m-%dT%H:%MZ") + timedelta(hours=3), 
                        "ch_key": ch_key
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
                m3u += f'#EXTINF:-1 tvg-id="CHOIX.{i}",CHOIX {i}\nhttp://{host}/api/stream/{i}\n'
            self.wfile.write(m3u.encode('utf-8'))
        else:
            self.generate_xml_output()

    def generate_xml_output(self):
        chans = self.get_organized_events()
        now = datetime.utcnow()
        self.send_response(200); self.send_header('Content-type', 'application/xml; charset=utf-8'); self.end_headers()
        
        output = '<?xml version="1.0" encoding="UTF-8"?>\n<tv>'
        
        for i in range(1, 6):
            output += f'\n<channel id="CHOIX.{i}"><display-name>CHOIX {i}</display-name></channel>'
            cursor = now - timedelta(hours=6)
            
            for p in sorted(chans[i], key=lambda x: x['start']):
                st, en = p['start'].strftime("%Y%m%d%H%M%S"), p['stop'].strftime("%Y%m%d%H%M%S")
                info = CH_DATABASE.get(p['ch_key'], {})
                ch_n = info.get('name', p['ch_key'] if p['ch_key'] else "A CONFIRMER")
                
                # Sélection de l'icône sport pour le titre
                lg_type = "soccer" if any(x in p['league'] for x in ["eng", "uefa", "usa"]) else p['league']
                icon = SPORT_ICONS.get(lg_type, SPORT_ICONS['default'])
                
                # Titre sécurisé
                safe_title = escape_xml(f"{icon} {p['title']} ({info.get('lang', '??')}) | {ch_n}")
                safe_ch_name = escape_xml(ch_n)
                
                if p['start'] > cursor:
                    output += f'\n<programme start="{cursor.strftime("%Y%m%d%H%M%S")} +0000" stop="{st} +0000" channel="CHOIX.{i}"><title>Suivant: {safe_title}</title></programme>'
                
                output += f'\n<programme start="{st} +0000" stop="{en} +0000" channel="CHOIX.{i}">'
                output += f'\n  <title>{safe_title}</title>'
                output += f'\n  <desc>Source: {safe_ch_name}</desc>'
                # BALISE ICON SRC SUPPRIMÉE ICI
                output += '\n</programme>'
                
                cursor = p['stop']
        
        output += '\n</tv>'
        self.wfile.write(output.encode('utf-8'))
