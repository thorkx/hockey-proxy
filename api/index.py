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
        "nhl": 500, 
        "nba": 400, 
        "uefa.champions": 375,
        "eng.1": 350,  # Premier League
        "fra.1": 350,  # Ligue 1
        "ita.1": 350,  # Serie A
        "esp.1": 350,  # LaLiga
        "uefa.europa": 350,
        "mlb": 300,    # Sous le foot européen comme demandé
        "usa.1": 250
    },
    "TEAMS": {
        "CANADIENS": 1000, 
        "RAPTORS": 1000, 
        "BLUE JAYS": 1000, 
        "CF MONTREAL": 1000, 
        "WREXHAM": 1200  # Priorité absolue pour ton équipe spécifique
    },
    "CHANNELS": {
        "BONUS_ENGLISH_PREMIUM": 500,
        "BONUS_FRENCH": 150,
        "PENALTY_TVA": -800
    }
}

# Équipes spécifiques à chercher dans des ligues non-standards
SPECIAL_TEAMS_SCAN = {
    "WREXHAM": ("soccer", "eng.3") 
}

# ==========================================
#              BASE DE DONNÉES
# ==========================================
BIBLE_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

CH_DATABASE = {
    "I1000.49609.schedulesdirect.org": {"name": "RDS", "id": "184813", "lang": "FR"},
    "I192.73271.schedulesdirect.org": {"name": "RDS2", "id": "184814", "lang": "FR"},
    "I124.39080.schedulesdirect.org": {"name": "RDS Info", "id": "184815", "lang": "FR"},
    "I193.73142.schedulesdirect.org": {"name": "TVA Sports", "id": "184811", "lang": "FR"},
    "I1884.90206.schedulesdirect.org": {"name": "TVA Sports 2", "id": "184812", "lang": "EN"},
    "I405.62111.schedulesdirect.org": {"name": "Sportsnet 4K", "id": "157674", "lang": "EN"},
    "SNOne": {"name": "SN One", "id": "157675", "lang": "EN"},
    "SN360": {"name": "SN 360", "id": "71517", "lang": "EN"},
    "SNEast": {"name": "SN East", "id": "71518", "lang": "EN"},
    "SNOntario": {"name": "SN Ontario", "id": "71519", "lang": "EN"},
    "SNWest": {"name": "SN West", "id": "71521", "lang": "EN"},
    "SNPacific": {"name": "SN Pacific", "id": "71520", "lang": "EN"},
    "SNWorld": {"name": "SN World", "id": "71526", "lang": "EN"},
    "I409.68858.schedulesdirect.org": {"name": "TSN 1", "id": "71234", "lang": "EN"},
    "TSN2": {"name": "TSN 2", "id": "71235", "lang": "EN"},
    "TSN3": {"name": "TSN 3", "id": "71236", "lang": "EN"},
    "TSN4": {"name": "TSN 4", "id": "71237", "lang": "EN"},
    "TSN5": {"name": "TSN 5", "id": "71238", "lang": "EN"},
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
    "BeInSports 1": {"name": "BeIn Sports 1", "id": "49895", "lang": "FR"},
    "BeInSports 2": {"name": "BeIn Sports 2", "id": "49896", "lang": "FR"},
    "BeInSports 3": {"name": "BeIn Sports 3", "id": "49897", "lang": "FR"},
    "CanalPlus.fr": {"name": "Canal+", "id": "49943", "lang": "FR"},
    "Canal+ Foot": {"name": "Canal+ Foot", "id": "49945", "lang": "FR"},
    "Canal+ Sport": {"name": "Canal+ Sport", "id": "49951", "lang": "FR"},
    "Canal+ Sport 360": {"name": "Canal+ Sport 360", "id": "49953", "lang": "FR"},
    "EuroSport 1": {"name": "EuroSport 1", "id": "50016", "lang": "FR"},
    "EuroSport 2": {"name": "EuroSport 2", "id": "50017", "lang": "FR"},
    "L'Equipe": {"name": "L'Equipe", "id": "50058", "lang": "FR"},
    "RMCSports 1": {"name": "RMC Sports 1", "id": "50145", "lang": "FR"},
    "RMCSports 2": {"name": "RMC Sports 2", "id": "50147", "lang": "FR"},
    "DAZN 1": {"name": "DAZN 1", "id": "44265", "lang": "ES"},
    "DAZN 2": {"name": "DAZN 2", "id": "44266", "lang": "ES"},
    "DAZN LaLiga": {"name": "DAZN LaLiga", "id": "44268", "lang": "ES"},
    "LaLiga TV": {"name": "LaLiga TV", "id": "44321", "lang": "ES"}
}

# Mise à jour des IDs prioritaires pour inclure les nouveaux réseaux
PREMIUM_IDS = [
    "Sportsnet (4K)", "SNOne", "SN360", "SNEast", "SNOntario", "SNWest", "SNPacific", "SNWorld",
    "TSN1", "TSN2", "TSN3", "TSN4", "TSN5", "ESPN", "ESPN2", "Canal+", "Canal+ Sport", "Sky Sport Premier League"
]

SPORT_ICONS = {
    "nhl": "🏒", "nba": "🏀", "mlb": "⚾", 
    "soccer": "⚽", "uefa.champions": "🇪🇺", "default": "🏆"
}

# ==========================================
#                UTILITAIRES
# ==========================================
def escape_xml(text):
    """Encodage numérique total pour compatibilité Chillio maximale"""
    if not text: return ""
    text = html.escape(text)
    return text.encode('ascii', 'xmlcharrefreplace').decode()

def clean_name(t):
    if not t: return ""
    t = t.upper()
    t = re.sub(r'HOCKEY|LNH|NBA|SOCCER|FOOTBALL| AT | VS |CONTRE', ' ', t)
    t = re.sub(r'[ÉÈÊË]', 'E', t); t = re.sub(r'[ÀÂÄ]', 'A', t)
    return re.sub(r'[^\w\s]', ' ', t)

def find_match_in_bible(ev_name, bible_data, ev_date_str):
    ev_time = datetime.strptime(ev_date_str, "%Y-%m-%dT%H:%MZ")
    keywords = [w for w in clean_name(ev_name).split() if len(w) > 3 and w not in ["MONTREAL", "TORONTO", "UNITED", "CITY"]]
    matches = []
    for prog in bible_data:
        try:
            raw_start = prog['start'].split(' ')[0]
            p_start = datetime.strptime(raw_start, "%Y%m%d%H%M%S")
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

# ==========================================
#                SERVEUR HTTP
# ==========================================
class handler(BaseHTTPRequestHandler):
    def get_organized_events(self):
        try: bible = requests.get(BIBLE_URL, timeout=5).json()
        except: bible = []
        now = datetime.utcnow()
        events, seen = [], set()
        
        # Liste des ligues à scanner
        leagues = [
            ("hockey","nhl"), ("basketball","nba"), ("baseball","mlb"),
            ("soccer","eng.1"), ("soccer","fra.1"), ("soccer","ita.1"),
            ("soccer","esp.1"), ("soccer","usa.1"), ("soccer","uefa.champions"),
            ("soccer","uefa.europa")
        ]
        
        # Ajout des ligues pour équipes spéciales (Wrexham)
        for t_name, l_info in SPECIAL_TEAMS_SCAN.items():
            if l_info not in leagues: leagues.append(l_info)

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
                    
                    # Filtre spécial pour les ligues de bas niveau (ne garder que l'équipe voulue)
                    is_low_league = lg in [info[1] for info in SPECIAL_TEAMS_SCAN.values() if info[1] not in ["eng.1", "usa.1"]]
                    if is_low_league:
                        if not any(team in name for team in SPECIAL_TEAMS_SCAN.keys()):
                            continue

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
            try:
                idx = int(self.path.split('/')[-1])
                chans = self.get_organized_events()
                now = datetime.utcnow()
                sid = "184813" # Défaut RDS
                
                for m in chans.get(idx, []):
                    if m['start'] <= now <= m['stop']:
                        sid = CH_DATABASE.get(m['ch_key'], {}).get("id", "184813")
                        break
                
                # Redirection avec forçage de non-cache pour permettre le switch de source
                self.send_response(302)
                self.send_header('Location', f"{STREAM_BASE}/{sid}")
                self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                self.send_header('Pragma', 'no-cache')
                self.send_header('Expires', '0')
                self.end_headers()
            except:
                self.send_response(302); self.send_header('Location', f"{STREAM_BASE}/184813"); self.end_headers()

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
        
        xml_out = '<?xml version="1.0" encoding="UTF-8"?>\n<tv>'
        for i in range(1, 6):
            xml_out += f'\n<channel id="CHOIX.{i}"><display-name>CHOIX {i}</display-name></channel>'
            cursor = now - timedelta(hours=6)
            for p in sorted(chans[i], key=lambda x: x['start']):
                st = p['start'].strftime("%Y%m%d%H%M%S") + " +0000"
                en = p['stop'].strftime("%Y%m%d%H%M%S") + " +0000"
                
                info = CH_DATABASE.get(p['ch_key'], {})
                ch_name = info.get('name', p['ch_key'] if p['ch_key'] else "A CONFIRMER")
                
                lg_type = "soccer" if any(x in p['league'] for x in ["eng", "uefa", "usa", "fra", "ita", "esp"]) else p['league']
                icon_emoji = SPORT_ICONS.get(lg_type, SPORT_ICONS['default'])
                
                safe_title = escape_xml(f"{icon_emoji} {p['title']} ({info.get('lang', '??')}) | {ch_name}")
                
                if p['start'] > cursor:
                    c_str = cursor.strftime("%Y%m%d%H%M%S") + " +0000"
                    xml_out += f'\n<programme start="{c_str}" stop="{st}" channel="CHOIX.{i}"><title>Suivant: {safe_title}</title></programme>'
                
                xml_out += f'\n<programme start="{st}" stop="{en}" channel="CHOIX.{i}">'
                xml_out += f'\n  <title>{safe_title}</title>'
                xml_out += f'\n  <desc>Diffuseur: {escape_xml(ch_name)}</desc>'
                xml_out += '\n</programme>'
                cursor = p['stop']
        
        xml_out += '\n</tv>'
        encoded_xml = xml_out.encode('utf-8')
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/xml; charset=utf-8')
        self.send_header('Content-Length', str(len(encoded_xml)))
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.end_headers()
        self.wfile.write(encoded_xml)
        
