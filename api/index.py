from http.server import BaseHTTPRequestHandler, HTTPServer
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
        "nhl": 800, "nba": 400, "uefa.champions": 375,
        "eng.1": 350, "fra.1": 350, "ita.1": 350, "esp.1": 350,
        "uefa.europa": 350, "mlb": 300, "usa.1": 250
    },
    "TEAMS": {
        "CANADIENS": 3500, "RAPTORS": 1000, "BLUE JAYS": 1000, 
        "CF MONTREAL": 1000, "WREXHAM": 1200
    },
    "CHANNELS": {
        "BONUS_HOCKEY_CANADA": 1200, 
        "BONUS_ENGLISH_PREMIUM": 500, 
        "BONUS_FRENCH": 300, 
        "PENALTY_TVA": -150 
    }
}

CANADA_HOCKEY_IDS = [
    "I123.15676.schedulesdirect.org", "I192.73271.schedulesdirect.org",
    "I409.68858.schedulesdirect.org", "TSN2", "TSN3", "TSN4", "TSN5",
    "I405.62111.schedulesdirect.org", "I406.18798.schedulesdirect.org",
    "SNOne", "SN360", "I406.18798.schedulesdirect.org", "SNOntario", "SNWest", "SNPacific"
]

# ==========================================
#              BASE DE DONNÉES
# ==========================================
BIBLE_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

# (Garder ton dictionnaire CH_DATABASE complet ici)
CH_DATABASE = {
    "I123.15676.schedulesdirect.org": {"name": "RDS", "id": "184813", "lang": "FR"},
    "I192.73271.schedulesdirect.org": {"name": "RDS2", "id": "184814", "lang": "FR"},
    "I124.39080.schedulesdirect.org": {"name": "RDS Info", "id": "184815", "lang": "FR"},
    "I193.73142.schedulesdirect.org": {"name": "TVA Sports", "id": "184811", "lang": "FR"},
    "I1884.90206.schedulesdirect.org": {"name": "TVA Sports 2", "id": "184812", "lang": "EN"},
    "I405.62111.schedulesdirect.org": {"name": "Sportsnet 4K", "id": "157674", "lang": "EN"},
    "I409.68858.schedulesdirect.org": {"name": "Sportsnet One", "id": "157675", "lang": "EN"},
    "I410.49952.schedulesdirect.org": {"name": "Sportsnet 360", "id": "71517", "lang": "EN"},
    "I406.18798.schedulesdirect.org": {"name": "Sportsnet East", "id": "71518", "lang": "EN"},
    "I408.18800.schedulesdirect.org": {"name": "Sportsnet West", "id": "71521", "lang": "EN"},
    "I407.18801.schedulesdirect.org": {"name": "Sportsnet Pacific", "id": "71520", "lang": "EN"},
    "I420.57735.schedulesdirect.org": {"name": "Sportsnet World", "id": "71526", "lang": "EN"},
    "I401.18990.schedulesdirect.org": {"name": "TSN 2", "id": "71235", "lang": "EN"},
    "I402.90118.schedulesdirect.org": {"name": "TSN 3", "id": "71236", "lang": "EN"},
    "I403.90122.schedulesdirect.org": {"name": "TSN 4", "id": "71237", "lang": "EN"},
    "I404.90124.schedulesdirect.org": {"name": "TSN 5", "id": "71238", "lang": "EN"},
    "OneSoccer": {"name": "OneSoccer", "id": "19320", "lang": "EN"},
    "ESPN": {"name": "ESPN", "id": "18345", "lang": "EN"},
    "ESPN2": {"name": "ESPN 2", "id": "18346", "lang": "EN"},
    "ESPNDeportes": {"name": "ESPN Deportes", "id": "18356", "lang": "ES"},
    "beINSPORTS1.fr": {"name": "BeIn Sports 1", "id": "49895", "lang": "FR"},
    "CanalPlus.fr": {"name": "Canal+", "id": "49943", "lang": "FR"},
    "L'Equipe": {"name": "L'Equipe", "id": "50058", "lang": "FR"},
    "DAZN 1": {"name": "DAZN 1", "id": "44265", "lang": "ES"}
}

SPORT_ICONS = {"nhl": "🏒", "nba": "🏀", "mlb": "⚾", "soccer": "⚽", "uefa.champions": "🇪🇺", "default": "🏆"}

# ==========================================
#                UTILITAIRES
# ==========================================
def escape_xml(text):
    if not text: return ""
    return html.escape(text).encode('ascii', 'xmlcharrefreplace').decode()

def clean_name(t):
    if not t: return ""
    t = t.upper()
    t = re.sub(r'HOCKEY|LNH|NBA|SOCCER|FOOTBALL| AT | VS |CONTRE', ' ', t)
    t = re.sub(r'[ÉÈÊË]', 'E', t); t = re.sub(r'[ÀÂÄ]', 'A', t)
    return re.sub(r'[^\w\s]', ' ', t)

def find_match_in_bible(ev_name, bible_data, ev_date_str):
    try:
        ev_time = datetime.strptime(ev_date_str, "%Y-%m-%dT%H:%MZ")
        current_teams = [w for w in clean_name(ev_name).split() if len(w) > 3 and w not in ["MONTREAL", "TORONTO", "UNITED", "CITY"]]
        potential_matches = []
        for prog in bible_data:
            p_start = datetime.strptime(prog['start'][:14], "%Y%m%d%H%M%S")
            # Fenêtre élargie à 6h (21600 sec) pour éviter les sauts en cours de match
            if abs((ev_time - p_start).total_seconds()) < 21600:
                title = clean_name(prog.get('title', ''))
                if any(team in title for team in current_teams):
                    potential_matches.append((prog['ch'], 500))
        if potential_matches:
            potential_matches.sort(key=lambda x: x[1], reverse=True)
            return potential_matches[0][0]
    except: pass
    return None

def fetch_espn(url):
    try: return requests.get(url, timeout=5).json()
    except: return {}

# ==========================================
#                SERVEUR HTTP
# ==========================================
class handler(BaseHTTPRequestHandler):
    def get_organized_events(self):
        try: bible = requests.get(BIBLE_URL, timeout=5).json()
        except: bible = []
        now = datetime.utcnow()
        events, seen = [], set()
        
        leagues = [
            ("hockey","nhl"), ("basketball","nba"), ("baseball","mlb"),
            ("soccer","eng.1"), ("soccer","fra.1"), ("soccer","ita.1"),
            ("soccer","esp.1"), ("soccer","usa.1"), ("soccer","uefa.champions")
        ]

        urls = []
        for day in range(2):
            ds = (now + timedelta(days=day)).strftime("%Y%m%d")
            for sp, lg in leagues:
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
                    
                    if lg == "nhl" and ch_key in CANADA_HOCKEY_IDS:
                        score += PRIORITY_CONFIG["CHANNELS"]["BONUS_HOCKEY_CANADA"]
                    
                    info = CH_DATABASE.get(ch_key, {})
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
                # Correction de la logique de collision pour accepter les matchs en cours
                if not any(not (e['stop'] <= ex['start'] or e['start'] >= ex['stop']) for ex in chans[i]):
                    chans[i].append(e); break
        return chans

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
                self.send_response(302); self.send_header('Location', f"{STREAM_BASE}/{sid}"); self.end_headers()
            except:
                self.send_response(302); self.send_header('Location', f"{STREAM_BASE}/184813"); self.end_headers()
        elif self.path.endswith('.m3u'):
            self.send_response(200); self.send_header('Content-type', 'text/plain'); self.end_headers()
            host = self.headers.get('Host')
            m3u = "#EXTM3U\n"
            for i in range(1,6):
                m3u += f'#EXTINF:-1 tvg-id="CHOIX.{i}",CHOIX {i}\nhttp://{host}/stream/{i}\n'
            self.wfile.write(m3u.encode('utf-8'))
        else:
            self.generate_xml_output()

    def generate_xml_output(self):
        chans = self.get_organized_events()
        now = datetime.utcnow()
        xml_out = '<?xml version="1.0" encoding="UTF-8"?>\n<tv>'
        for i in range(1, 6):
            xml_out += f'\n<channel id="CHOIX.{i}"><display-name>CHOIX {i}</display-name></channel>'
            # Curseur commence au début de la journée affichée
            cursor = now - timedelta(hours=12)
            for p in sorted(chans[i], key=lambda x: x['start']):
                st_str = p['start'].strftime("%Y%m%d%H%M%S") + " +0000"
                en_str = p['stop'].strftime("%Y%m%d%H%M%S") + " +0000"
                info = CH_DATABASE.get(p['ch_key'], {})
                ch_name = info.get('name', p['ch_key'] if p['ch_key'] else "À CONFIRMER")
                icon = SPORT_ICONS.get(p['league'], SPORT_ICONS['default'])
                safe_title = escape_xml(f"{icon} {p['title']} | {ch_name}")
                
                # FIX CRITIQUE : Ne crée un bloc "Suivant" que si le match n'est pas déjà commencé
                if p['start'] > now and p['start'] > cursor:
                    xml_out += f'\n<programme start="{cursor.strftime("%Y%m%d%H%M%S")} +0000" stop="{st_str}" channel="CHOIX.{i}"><title>À venir: {safe_title}</title></programme>'
                
                xml_out += f'\n<programme start="{st_str}" stop="{en_str}" channel="CHOIX.{i}"><title>{safe_title}</title><desc>Diffuseur: {ch_name} | Score: {p["score"]}</desc></programme>'
                cursor = p['stop']
        xml_out += '\n</tv>'
        self.send_response(200); self.send_header('Content-Type', 'application/xml; charset=utf-8'); self.end_headers()
        self.wfile.write(xml_out.encode('utf-8'))

if __name__ == "__main__":
    server = HTTPServer(('0.0.0.0', 5000), handler)
    print("Serveur Hockey Proxy Fixé sur le port 5000")
    server.serve_forever()
