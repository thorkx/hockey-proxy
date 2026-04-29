from http.server import BaseHTTPRequestHandler
import requests
import json
from datetime import datetime, timedelta

# CONFIGURATION
BIBLE_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

# NOMS SIMPLIFIÉS POUR L'AFFICHAGE
CH_NAMES = {
    "I123.15676.schedulesdirect.org": "RDS",
    "I124.15677.schedulesdirect.org": "RDS 2",
    "I154.58314.schedulesdirect.org": "TVA Sports",
    "I155.58315.schedulesdirect.org": "TVA Sports 2",
    "I410.18802.schedulesdirect.org": "SN Ontario",
    "I409.18801.schedulesdirect.org": "SN East",
    "I408.18800.schedulesdirect.org": "SN West",
    "I411.18803.schedulesdirect.org": "SN Pacific",
    "I412.18804.schedulesdirect.org": "SN One",
    "I413.18805.schedulesdirect.org": "SN 360",
    "I111.15670.schedulesdirect.org": "TSN 1",
    "I112.15671.schedulesdirect.org": "TSN 2",
    "I113.15672.schedulesdirect.org": "TSN 3",
    "I114.15673.schedulesdirect.org": "TSN 4",
    "I115.15674.schedulesdirect.org": "TSN 5",
    "I446.52300.schedulesdirect.org": "Sky MX / La Liga",
    "I212.12345.schedulesdirect.org": "DAZN",
    "I900.00001.schedulesdirect.org": "Apple TV MLS"
}

# MAPPING DES FLUX
STREAM_MAP = {
    "I123.15676.schedulesdirect.org": "71151",
    "I124.15677.schedulesdirect.org": "71152",
    "I154.58314.schedulesdirect.org": "71165",
    "I155.58315.schedulesdirect.org": "71166",
    "I410.18802.schedulesdirect.org": "71236",
    "I409.18801.schedulesdirect.org": "71234",
    "I408.18800.schedulesdirect.org": "71237",
    "I411.18803.schedulesdirect.org": "71235",
    "I412.18804.schedulesdirect.org": "71233",
    "I413.18805.schedulesdirect.org": "71232",
    "I111.15670.schedulesdirect.org": "71243",
    "I112.15671.schedulesdirect.org": "71244",
    "I113.15672.schedulesdirect.org": "71245",
    "I114.15673.schedulesdirect.org": "71246",
    "I115.15674.schedulesdirect.org": "71247",
    "I446.52300.schedulesdirect.org": "71239",
    "I212.12345.schedulesdirect.org": "71261",
    "I900.00001.schedulesdirect.org": "71270"
}

def get_match_score(name, sport, league):
    n = name.upper()
    if any(k in n for k in ["CANADIENS", "MONTREAL CANADIENS", "HABS"]): return 1000
    if "CF MONTREAL" in n: return 950
    if any(k in n for k in ["BLUE JAYS", "JAYS"]): return 900
    if any(k in n for k in ["F1", "FORMULA 1", "GRAND PRIX"]): return 850
    if "CANADA" in n and sport == "soccer": return 800
    if "MANCHESTER CITY" in n or "MAN CITY" in n: return 750
    if "PARIS SAINT-GERMAIN" in n or "PSG" in n: return 700
    if "RAPTORS" in n: return 650
    if league in ["fifa.friendly", "uefa.nations", "fifa.world", "uefa.euro"]: return 600
    if "BOLOGNA" in n: return 550
    if "WREXHAM" in n: return 500
    if sport == "hockey": return 450
    if league == "usa.1": return 400
    if "YANKEES" in n: return 350
    if "DODGERS" in n: return 340
    if "LAKERS" in n: return 330
    if league in ["eng.1", "fra.1", "esp.1", "ita.1"]: return 250
    if sport == "baseball": return 200
    if sport == "basketball": return 150
    return 10

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.endswith('.m3u'):
            self.generate_m3u()
        else:
            self.generate_xml()

    def generate_xml(self):
        try:
            bible = requests.get(BIBLE_URL, headers={'Cache-Control': 'no-cache'}, timeout=10).json()
        except: bible = []

        final_selection = []
        now_utc = datetime.utcnow()
        soccer_leagues = ["eng.1", "fra.1", "esp.1", "ita.1", "usa.1", "uefa.champions"]
        
        for day_offset in range(4):
            target_date = (now_utc + timedelta(days=day_offset)).strftime("%Y%m%d")
            urls = [("hockey", "nhl", "🏒"), ("baseball", "mlb", "⚾"), ("basketball", "nba", "🏀")]
            for sl in soccer_leagues: urls.append(("soccer", sl, "⚽"))
            
            for sport, league, icon in urls:
                api_url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard?dates={target_date}"
                try:
                    res = requests.get(api_url, timeout=5).json()
                    for event in res.get('events', []):
                        name = event.get('name', '').upper()
                        espn_time = datetime.strptime(event.get('date'), "%Y-%m-%dT%H:%MZ")
                        score = get_match_score(name, sport, league)
                        
                        matching_progs = []
                        teams = name.replace(' AT ', ' ').replace(' @ ', ' ').split(' ')
                        clean_teams = [t for t in teams if len(t) > 3]

                        for prog in bible:
                            try:
                                p_start = datetime.strptime(prog.get('start', '')[:14], "%Y%m%d%H%M%S")
                                if abs((espn_time - p_start).total_seconds()) / 3600 <= 2.0:
                                    if any(t in prog.get('title', '').upper() or t in prog.get('desc', '').upper() for t in clean_teams):
                                        matching_progs.append(prog)
                            except: continue

                        if matching_progs:
                            primary = next((p for p in matching_progs if p['ch'] in STREAM_MAP), matching_progs[0])
                            sid = STREAM_MAP.get(primary['ch'], "71151")
                            u_channels = [CH_NAMES.get(p['ch'], p['name']) for p in matching_progs]
                            title = f"{icon} {event.get('name')} [{' | '.join(list(dict.fromkeys(u_channels))[:4])}]"
                            start, stop = primary['start'][:14], primary['stop'][:14]
                        else:
                            sid, start, stop = "71151", espn_time.strftime("%Y%m%d%H%M%S"), (espn_time + timedelta(hours=3)).strftime("%Y%m%d%H%M%S")
                            title = f"{icon} {event.get('name')} [À CONFIRMER]"

                        final_selection.append({"title": title, "sid": sid, "start": start, "stop": stop, "priority": score})
                except: continue

        final_selection.sort(key=lambda x: x['priority'], reverse=True)
        channels = {i: [] for i in range(1, 6)}
        for m in final_selection:
            for i in range(1, 6):
                if not any(not (m['stop'] <= ex['start'] or m['start'] >= ex['stop']) for ex in channels[i]):
                    channels[i].append(m); break

        self.send_response(200)
        self.send_header('Content-type', 'application/xml; charset=utf-8')
        self.end_headers()
        xml = '<?xml version="1.0" encoding="UTF-8"?><tv>'
        for i in range(1, 6):
            xml += f'<channel id="CHOIX.{i}"><display-name>CHOIX {i}</display-name></channel>'
            for p in channels[i]:
                xml += f'<programme start="{p["start"]} +0000" stop="{p["stop"]} +0000" channel="CHOIX.{i}"><title>{p["title"].replace("&", "&amp;")}</title></programme>'
        self.wfile.write((xml + '</tv>').encode('utf-8'))

    def generate_m3u(self):
        self.send_response(200)
        # CHANGEMENT ICI : text/plain pour forcer l'affichage dans le navigateur
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        m3u = "#EXTM3U\n"
        for i in range(1, 6):
            m3u += f'#EXTINF:-1 tvg-id="CHOIX_{i}" tvg-name="CHOIX_{i}" group-title="REGIE SPORT",CHOIX {i}\n'
            m3u += f'{STREAM_BASE}/71151?canal=ch{i}\n'
        self.wfile.write(m3u.encode('utf-8'))
        
