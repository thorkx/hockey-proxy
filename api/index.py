from http.server import BaseHTTPRequestHandler
import requests
import json
from datetime import datetime, timedelta

# CONFIGURATION
BIBLE_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

# HIÉRARCHIE STRICTE (Poids dégressifs basés sur ta liste)
def get_match_score(name, sport, league):
    n = name.upper()
    # 1. Canadiens (Priorité absolue)
    if any(k in n for k in ["CANADIENS", "MONTREAL CANADIENS", "HABS"]): return 1000
    # 2. CF Montréal
    if "CF MONTREAL" in n: return 950
    # 3. Blue Jays
    if any(k in n for k in ["BLUE JAYS", "JAYS"]): return 900
    # 4. F1
    if any(k in n for k in ["F1", "FORMULA 1", "GRAND PRIX"]): return 850
    # 5. Foot international canadien
    if "CANADA" in n and sport == "soccer": return 800
    # 6. Manchester City
    if "MANCHESTER CITY" in n or "MAN CITY" in n: return 750
    # 7. Paris Saint Germain
    if "PARIS SAINT-GERMAIN" in n or "PSG" in n: return 700
    # 8. Raptors
    if "RAPTORS" in n: return 650
    # 9. Foot international
    if league in ["fifa.friendly", "uefa.nations", "fifa.world", "uefa.euro"]: return 600
    # 10. Bologna
    if "BOLOGNA" in n: return 550
    # 11. Wrexham
    if "WREXHAM" in n: return 500
    # 12. Tout le reste du hockey
    if sport == "hockey": return 450
    # 13. Tout le reste MLS
    if league == "usa.1": return 400
    # 14. Yankees / Dodgers / Lakers
    if "YANKEES" in n: return 350
    if "DODGERS" in n: return 340
    if "LAKERS" in n: return 330
    # 15. Soccer Européen (PL, L1, Liga, Serie A)
    if league in ["eng.1", "fra.1", "esp.1", "ita.1"]: return 250
    # 16. Reste MLB
    if sport == "baseball": return 200
    # 17. Reste NBA
    if sport == "basketball": return 150
    
    return 10

LEAGUES_MAP = {
    "hockey": "nhl",
    "baseball": "mlb",
    "soccer": "eng.1", # On bouclera sur plusieurs ligues
    "basketball": "nba"
}

CH_NAMES = {
    "I408.18800.schedulesdirect.org": "SN West",
    "I123.15676.schedulesdirect.org": "RDS",
    "I111.15670.schedulesdirect.org": "TSN",
    "I154.58314.schedulesdirect.org": "TVA Sports"
}

STREAM_MAP = {
    "I408.18800.schedulesdirect.org": "71520",
    "I123.15676.schedulesdirect.org": "184813",
    "I111.15670.schedulesdirect.org": "184816",
    "I154.58314.schedulesdirect.org": "184821"
}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            bible = requests.get(BIBLE_URL, headers={'Cache-Control': 'no-cache'}, timeout=10).json()
        except: bible = []

        final_selection = []
        now_utc = datetime.utcnow()
        
        # On élargit les ligues pour le soccer
        soccer_leagues = ["eng.1", "fra.1", "esp.1", "ita.1", "usa.1", "uefa.champions"]
        
        for day_offset in range(4):
            target_date = (now_utc + timedelta(days=day_offset)).strftime("%Y%m%d")
            
            # Construction de la liste des URLs à appeler
            urls = [
                ("hockey", "nhl", "🏒"),
                ("baseball", "mlb", "⚾"),
                ("basketball", "nba", "🏀")
            ]
            for sl in soccer_leagues: urls.append(("soccer", sl, "⚽"))
            
            for sport, league, icon in urls:
                api_url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard?dates={target_date}"
                try:
                    res = requests.get(api_url, timeout=5).json()
                    for event in res.get('events', []):
                        name = event.get('name', '').upper()
                        espn_time = datetime.strptime(event.get('date'), "%Y-%m-%dT%H:%MZ")
                        score = get_match_score(name, sport, league)
                        
                        # Matching Bible
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
                            sid = STREAM_MAP.get(primary['ch'], "184813")
                            u_channels = []
                            for p in matching_progs:
                                nm = CH_NAMES.get(p['ch'], p['name'])
                                if nm not in u_channels: u_channels.append(nm)
                            title = f"{icon} {event.get('name')} [{' | '.join(u_channels)}]"
                            start, stop = primary['start'][:14], primary['stop'][:14]
                        else:
                            sid, start, stop = "184813", espn_time.strftime("%Y%m%d%H%M%S"), (espn_time + timedelta(hours=3)).strftime("%Y%m%d%H%M%S")
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
