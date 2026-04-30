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
        "BONUS_HOCKEY_CANADA": 1200, # RDS, TSN, SN
        "BONUS_ENGLISH_PREMIUM": 500, 
        "BONUS_FRENCH": 300, 
        "PENALTY_TVA": -150 # Préfère RDS mais garde TVA si c'est tout ce qu'il y a
    }
}

CANADA_HOCKEY_IDS = [
    "I123.15676.schedulesdirect.org", "I192.73271.schedulesdirect.org",
    "I409.68858.schedulesdirect.org", "TSN2", "TSN3", "TSN4", "TSN5",
    "I405.62111.schedulesdirect.org", "I406.18798.schedulesdirect.org",
    "SNOne", "SN360", "SNEast", "SNOntario", "SNWest", "SNPacific"
]

SPECIAL_TEAMS_SCAN = {"WREXHAM": ("soccer", "eng.3")}

# ==========================================
#              BASE DE DONNÉES
# ==========================================
BIBLE_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

CH_DATABASE = {
    "I123.15676.schedulesdirect.org": {"name": "RDS", "id": "184813", "lang": "FR"},
    "I192.73271.schedulesdirect.org": {"name": "RDS2", "id": "184814", "lang": "FR"},
    "I124.39080.schedulesdirect.org": {"name": "RDS Info", "id": "184815", "lang": "FR"},
    "I193.73142.schedulesdirect.org": {"name": "TVA Sports", "id": "184811", "lang": "FR"},
    "I1884.90206.schedulesdirect.org": {"name": "TVA Sports 2", "id": "184812", "lang": "EN"},
    "I405.62111.schedulesdirect.org": {"name": "Sportsnet 4K", "id": "157674", "lang": "EN"},
    "I409.68858.schedulesdirect.org": {"name": "SN One", "id": "157675", "lang": "EN"},
    "I410.49952.schedulesdirect.org": {"name": "SN 360", "id": "71517", "lang": "EN"},
    "I406.18798.schedulesdirect.org": {"name": "SN East", "id": "71518", "lang": "EN"},
    "I408.18800.schedulesdirect.org": {"name": "SN West", "id": "71521", "lang": "EN"},
    "I407.18801.schedulesdirect.org": {"name": "SN Pacific", "id": "71520", "lang": "EN"},
    "I420.57735.schedulesdirect.org": {"name": "SN World", "id": "71526", "lang": "EN"},
    "I401.18990.schedulesdirect.org": {"name": "TSN 2", "id": "71235", "lang": "EN"},
    "I402.90118.schedulesdirect.org": {"name": "TSN 3", "id": "71236", "lang": "EN"},
    "I403.90122.schedulesdirect.org": {"name": "TSN 4", "id": "71237", "lang": "EN"},
    "I404.90124.schedulesdirect.org": {"name": "TSN 5", "id": "71238", "lang": "EN"},
    "OneSoccer": {"name": "OneSoccer", "id": "19320", "lang": "EN"},
    "ESPN": {"name": "ESPN", "id": "18345", "lang": "EN"},
    "ESPN2": {"name": "ESPN 2", "id": "18346", "lang": "EN"},
    "ESPNDeportes": {"name": "ESPN Deportes", "id": "18356", "lang": "ES"},
    "BeInSports": {"name": "BeIn Sports", "id": "71320", "lang": "EN"},
    "BeInSports USA": {"name": "BeIn Sports USA", "id": "18312", "lang": "EN"},
    "BeInSports Xtra": {"name": "BeIn Sports Xtra", "id": "19489", "lang": "EN"},
    "CBS Sports": {"name": "CBS Sports", "id": "18335", "lang": "EN"},
    "FoxSports1": {"name": "Fox Sports 1", "id": "18242", "lang": "EN"},
    "FoxSports2": {"name": "Fox Sports 2", "id": "18366", "lang": "EN"},
    "Golazo Sports": {"name": "Golazo Sports", "id": "18333", "lang": "EN"},
    "Marquee Sports": {"name": "Marquee Sports", "id": "18355", "lang": "EN"},
    "MSG": {"name": "MSG", "id": "18351", "lang": "EN"},
    "MSG Plus": {"name": "MSG Plus", "id": "18352", "lang": "EN"},
    "YES Network": {"name": "YES Network", "id": "18354", "lang": "EN"},
    "Sky Eurosport 1": {"name": "Sky Eurosport 1", "id": "74248", "lang": "EN"},
    "Sky Eurosport 2": {"name": "Sky Eurosport 2", "id": "74251", "lang": "EN"},
    "Sky Premier Sport 1": {"name": "Sky Premier Sport 1", "id": "74272", "lang": "EN"},
    "Sky Sport F1": {"name": "Sky Sport F1", "id": "74316", "lang": "EN"},
    "Sky Sport Golf": {"name": "Sky Sport Golf", "id": "74319", "lang": "EN"},
    "Sky Sport Main Event": {"name": "Sky Sport Main Event", "id": "74322", "lang": "EN"},
    "Sky Sport Mix": {"name": "Sky Sport Mix", "id": "74325", "lang": "EN"},
    "Sky Sport News": {"name": "Sky Sport News", "id": "74328", "lang": "EN"},
    "Sky Sport Premier League": {"name": "Sky Sport Premier League", "id": "74331", "lang": "EN"},
    "TNT Sports 1": {"name": "TNT Sports 1", "id": "74357", "lang": "EN"},
    "TNT Sports 2": {"name": "TNT Sports 2", "id": "74360", "lang": "EN"},
    "TNT Sports 3": {"name": "TNT Sports 3", "id": "74363", "lang": "EN"},
    "TNT Sports 4": {"name": "TNT Sports 4", "id": "74366", "lang": "EN"},
    "Viaplay Sports 1": {"name": "Viaplay Sports 1", "id": "74378", "lang": "EN"},
    "Viaplay Sports 2": {"name": "Viaplay Sports 2", "id": "74381", "lang": "EN"},
    "beINSPORTS1.fr": {"name": "BeIn Sports 1", "id": "49895", "lang": "FR"},
    "beINSPORTS2.fr": {"name": "BeIn Sports 2", "id": "49896", "lang": "FR"},
    "beINSPORTS3.fr": {"name": "BeIn Sports 3", "id": "49897", "lang": "FR"},
    "CanalPlus.fr": {"name": "Canal+", "id": "49943", "lang": "FR"},
    "CanalPlusFoot.fr": {"name": "Canal+ Foot", "id": "49945", "lang": "FR"},
    "CanalPlusSport.fr": {"name": "Canal+ Sport", "id": "49951", "lang": "FR"},
    "CanalPlusSport360.fr": {"name": "Canal+ Sport 360", "id": "49953", "lang": "FR"},
    "EuroSport1.fr": {"name": "EuroSport 1", "id": "50016", "lang": "FR"},
    "EuroSport2.fr": {"name": "EuroSport 2", "id": "50017", "lang": "FR"},
    "L'Equipe": {"name": "L'Equipe", "id": "50058", "lang": "FR"},
    "RMCSport1.fr": {"name": "RMC Sports 1", "id": "50145", "lang": "FR"},
    "RMCSport2.fr": {"name": "RMC Sports 2", "id": "50147", "lang": "FR"},
    "DAZN 1": {"name": "DAZN 1", "id": "44265", "lang": "ES"},
    "DAZN 2": {"name": "DAZN 2", "id": "44266", "lang": "ES"},
    "DAZN LaLiga": {"name": "DAZN LaLiga", "id": "44268", "lang": "ES"},
    "LaLiga TV": {"name": "LaLiga TV", "id": "44321", "lang": "ES"}
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
            p_start = datetime.strptime(prog['start'].split(' ')[0], "%Y%m%d%H%M%S")
            if abs((ev_time - p_start).total_seconds()) < 14400:
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
            cursor = now - timedelta(hours=6)
            for p in sorted(chans[i], key=lambda x: x['start']):
                st, en = p['start'].strftime("%Y%m%d%H%M%S") + " +0000", p['stop'].strftime("%Y%m%d%H%M%S") + " +0000"
                info = CH_DATABASE.get(p['ch_key'], {})
                ch_name = info.get('name', p['ch_key'] if p['ch_key'] else "À CONFIRMER")
                icon = SPORT_ICONS.get(p['league'], SPORT_ICONS['default'])
                safe_title = escape_xml(f"{icon} {p['title']} | {ch_name}")
                if p['start'] > cursor:
                    xml_out += f'\n<programme start="{cursor.strftime("%Y%m%d%H%M%S")} +0000" stop="{st}" channel="CHOIX.{i}"><title>Suivant: {safe_title}</title></programme>'
                xml_out += f'\n<programme start="{st}" stop="{en}" channel="CHOIX.{i}"><title>{safe_title}</title><desc>Diffuseur: {ch_name}</desc></programme>'
                cursor = p['stop']
        xml_out += '\n</tv>'
        self.send_response(200); self.send_header('Content-Type', 'application/xml; charset=utf-8'); self.end_headers()
        self.wfile.write(xml_out.encode('utf-8'))

if __name__ == "__main__":
    server = HTTPServer(('0.0.0.0', 5000), handler)
    print("Serveur Hockey Proxy démarré sur le port 5000")
    server.serve_forever()
    
