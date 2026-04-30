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
        "nhl": 800, "nba": 250, "uefa.champions": 375,
        "eng.1": 350, "fra.1": 350, "ita.1": 350, "esp.1": 350,
        "uefa.europa": 350, "mlb": 200, "usa.1": 450
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
    "SNOne", "SN360", "SNOntario", "SNWest", "SNPacific"
]

# ==========================================
#              BASE DE DONNÉES
# ==========================================
BIBLE_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"


CH_DATABASE = {
    # --- Canada ---
    "I123.15676.schedulesdirect.org": {"name": "RDS", "id": "184813", "lang": "FR"},
    "I192.73271.schedulesdirect.org": {"name": "RDS 2", "id": "184814", "lang": "FR"},
    "I124.39080.schedulesdirect.org": {"name": "RDS Info", "id": "184815", "lang": "FR"},
    "I193.73142.schedulesdirect.org": {"name": "TVA Sports", "id": "184811", "lang": "FR"},
    "I1884.90206.schedulesdirect.org": {"name": "TVA Sports 2", "id": "184812", "lang": "EN"},
    "I405.62111.schedulesdirect.org": {"name": "Sportsnet 4K", "id": "157674", "lang": "EN"},
    "I409.68858.schedulesdirect.org": {"name": "SN One", "id": "157675", "lang": "EN"},
    "I410.49952.schedulesdirect.org": {"name": "SN 360", "id": "71517", "lang": "EN"},
    "I406.18798.schedulesdirect.org": {"name": "SN East", "id": "71518", "lang": "EN"},
    "I408.18800.schedulesdirect.org": {"name": "SN West", "id": "71521", "lang": "EN"},
    "I407.18801.schedulesdirect.org": {"name": "SN Pacific", "id": "71520", "lang": "EN"},
    "I401.18990.schedulesdirect.org": {"name": "TSN 2", "id": "71235", "lang": "EN"},
    "I402.90118.schedulesdirect.org": {"name": "TSN 3", "id": "71236", "lang": "EN"},
    "I403.90122.schedulesdirect.org": {"name": "TSN 4", "id": "71237", "lang": "EN"},
    "I404.90124.schedulesdirect.org": {"name": "TSN 5", "id": "71238", "lang": "EN"},
    "One.Soccer.ca2": {"name": "OneSoccer", "id": "19320", "lang": "EN"},
    "I420.57735.schedulesdirect.org": {"name": "SN World", "id": "71526", "lang": "EN"},

    # --- France ---
    "CanalPlus.fr": {"name": "Canal+", "id": "49943", "lang": "FR"},
    "CanalPlusSport.fr": {"name": "Canal+ Sport", "id": "49951", "lang": "FR"},
    "CanalPlusSport360.fr": {"name": "Canal+ Sport 360", "id": "83038", "lang": "FR"},
    "beINSPORTS1.fr": {"name": "BeIn Sports 1", "id": "49895", "lang": "FR"},
    "beINSPORTS2.fr": {"name": "BeIn Sports 2", "id": "49896", "lang": "FR"},
    "beINSPORTS3.fr": {"name": "BeIn Sports 3", "id": "49897", "lang": "FR"},
    "beINSPORTSMAX4.fr": {"name": "BeIn Max 4", "id": "49903", "lang": "FR"},
    "beINSPORTSMAX5.fr": {"name": "BeIn Max 5", "id": "83080", "lang": "FR"},
    "beINSPORTSMAX6.fr": {"name": "BeIn Max 6", "id": "83081", "lang": "FR"},
    "beINSPORTSMAX7.fr": {"name": "BeIn Max 7", "id": "83082", "lang": "FR"},
    "beINSPORTSMAX8.fr": {"name": "BeIn Max 8", "id": "49904", "lang": "FR"},
    "beINSPORTSMAX9.fr": {"name": "BeIn Max 9", "id": "49905", "lang": "FR"},
    "beINSPORTSMAX10.fr": {"name": "BeIn Max 10", "id": "49906", "lang": "FR"},
    "Eurosport1.fr": {"name": "Eurosport 1", "id": "50009", "lang": "FR"},
    "Eurosport2.fr": {"name": "Eurosport 2", "id": "50010", "lang": "FR"},
    "RMCSport1.fr": {"name": "RMC Sport 1", "id": "50145", "lang": "FR"},
    "RMCSport2.fr": {"name": "RMC Sport 2", "id": "50147", "lang": "FR"},

    # --- UK ---
    "I1241.82450.schedulesdirect.org": {"name": "TNT Sports 1", "id": "74357", "lang": "EN"},
    "I1246.82451.schedulesdirect.org": {"name": "TNT Sports 2", "id": "74360", "lang": "EN"},
    "I1248.95772.schedulesdirect.org": {"name": "TNT Sports 3", "id": "74363", "lang": "EN"},
    "I1099.116645.schedulesdirect.org": {"name": "Sky PL", "id": "74322", "lang": "EN"},
    "I1081.87578.schedulesdirect.org": {"name": "Sky F1", "id": "74316", "lang": "EN"},

    # --- USA ---
    "I206.32645.schedulesdirect.org": {"name": "ESPN", "id": "18345", "lang": "EN"},
    "I209.45507.schedulesdirect.org": {"name": "ESPN 2", "id": "18346", "lang": "EN"},
    "I301.25595.schedulesdirect.org": {"name": "ESPN Deportes", "id": "18356", "lang": "ES"},
    "I219.82541.schedulesdirect.org": {"name": "FS1", "id": "18242", "lang": "EN"},
    "I221.16365.schedulesdirect.org": {"name": "CBS Sports", "id": "18335", "lang": "EN"},
    "I392.76942.gracenote.com": {"name": "BeIn USA", "id": "18312", "lang": "EN"}
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
    
def find_all_matches_in_bible(ev_name, bible_data, ev_date_str):
    found_keys = set()
    try:
        ev_date_clean = ev_date_str.split('T')
        ev_time = datetime.strptime(ev_date_clean[0] + ev_date_clean[1][:5], "%Y-%m-%d%H:%M")
        current_teams = [w for w in clean_name(ev_name).split() if len(w) > 3 and w not in ["MONTREAL", "TORONTO", "UNITED", "CITY"]]
        if "CANADIENS" in ev_name.upper() and "CANADIENS" not in current_teams:
            current_teams.append("CANADIENS")

        for prog in bible_data:
            raw_start = re.sub(r'\D', '', prog['start'])[:12]
            p_start = datetime.strptime(raw_start, "%Y%m%d%H%M")
            if abs((ev_time - p_start).total_seconds()) < 28800: # Fenêtre de 8h
                title = clean_name(prog.get('title', ''))
                desc = clean_name(prog.get('desc', ''))
                if any(team in title for team in current_teams) or any(team in desc for team in current_teams):
                    found_keys.add(prog['ch'])
    except: pass
    return list(found_keys)
    
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
                    
                    # ÉTAPE 1 : Trouver tous les hits potentiels dans la bible
                    all_possible_keys = find_all_matches_in_bible(name, bible, ev['date'])
                    if not all_possible_keys: continue

                    potential_channel_hits = []
                    for ch_key in all_possible_keys:
                        # Évaluation du score pour CHAQUE chaîne trouvée
                        temp_score = PRIORITY_CONFIG["LEAGUES"].get(lg, 100)
                        for team, bonus in PRIORITY_CONFIG["TEAMS"].items():
                            if team in name: temp_score += bonus
                        
                        if lg == "nhl" and ch_key in CANADA_HOCKEY_IDS:
                            temp_score += PRIORITY_CONFIG["CHANNELS"]["BONUS_HOCKEY_CANADA"]
                        
                        info = CH_DATABASE.get(ch_key, {})
                        is_soccer = any(x in lg for x in ["soccer", "eng.1", "fra.1", "uefa", "usa.1"])
                        
                        if info.get("lang") == "FR" and is_soccer:
                            temp_score += PRIORITY_CONFIG["CHANNELS"]["BONUS_FRENCH"]
                        
                        # Bonus Premium (TSN, Sportsnet, Sky...)
                        if ch_key in CANADA_HOCKEY_IDS or "Sky" in info.get("name", ""):
                            temp_score += PRIORITY_CONFIG["CHANNELS"]["BONUS_ENGLISH_PREMIUM"]

                        if ch_key and ("TVA" in str(ch_key).upper() or "184811" in str(ch_key)):
                            temp_score += PRIORITY_CONFIG["CHANNELS"]["PENALTY_TVA"]
                        
                        potential_channel_hits.append({"ch_key": ch_key, "score": temp_score})

                    # ÉTAPE 2 : Garder seulement le meilleur hit pour cet événement
                    potential_channel_hits.sort(key=lambda x: x['score'], reverse=True)
                    best_hit = potential_channel_hits[0]

                    events.append({
                        "title": name, "score": best_hit['score'], "league": lg,
                        "start": datetime.strptime(ev['date'], "%Y-%m-%dT%H:%MZ"), 
                        "stop": datetime.strptime(ev['date'], "%Y-%m-%dT%H:%MZ") + timedelta(hours=3), 
                        "ch_key": best_hit['ch_key']
                    })
                    seen.add(name)

        # ÉTAPE 3 : Compétition externe pour remplir la grille
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
            cursor = now - timedelta(hours=12)
            for p in sorted(chans[i], key=lambda x: x['start']):
                st_str = p['start'].strftime("%Y%m%d%H%M%S") + " +0000"
                en_str = p['stop'].strftime("%Y%m%d%H%M%S") + " +0000"
                info = CH_DATABASE.get(p['ch_key'], {})
                ch_name = info.get('name', p['ch_key'] if p['ch_key'] else "À CONFIRMER")
                icon = SPORT_ICONS.get(p['league'], SPORT_ICONS['default'])
                safe_title = escape_xml(f"{icon} {p['title']} | {ch_name}")
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
    
