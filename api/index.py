from http.server import BaseHTTPRequestHandler
import requests
import json
import time
from datetime import datetime, timedelta

# CONFIGURATION
BIBLE_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

# Mapping exact pour rediriger vers le bon flux selon ce qui est trouvé dans l'EPG
STREAM_MAP = {
    "I123.15676.schedulesdirect.org": "71151", "I124.15677.schedulesdirect.org": "71152",
    "I154.58314.schedulesdirect.org": "71165", "I155.58315.schedulesdirect.org": "71166",
    "I111.15670.schedulesdirect.org": "71243", "I112.15671.schedulesdirect.org": "71244",
    "I113.15672.schedulesdirect.org": "71245", "I114.15673.schedulesdirect.org": "71246",
    "I115.15674.schedulesdirect.org": "71247", "I410.18802.schedulesdirect.org": "71236",
    "I409.18801.schedulesdirect.org": "71234", "I446.52300.schedulesdirect.org": "71239"
}

CH_NAMES = {
    "I123.15676.schedulesdirect.org": "RDS", "I124.15677.schedulesdirect.org": "RDS 2",
    "I154.58314.schedulesdirect.org": "TVA Sports", "I155.58315.schedulesdirect.org": "TVA Sports 2",
    "I111.15670.schedulesdirect.org": "TSN 1"
}

def get_match_score(name):
    n = name.upper()
    if "CANADIENS" in n or "MONTREAL" in n or "HABS" in n: return 1000
    if "BLUE JAYS" in n or "TORONTO" in n: return 800
    if "F1" in n or "GRAND PRIX" in n: return 750
    return 100

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if "/stream/" in self.path:
            # Récupération de l'index du canal (1-5)
            try: channel_idx = int(self.path.split("/")[-1])
            except: channel_idx = 1
            # Redirection simplifiée vers RDS par défaut pour le moment
            self.send_response(302)
            self.send_header('Location', f"{STREAM_BASE}/71151")
            self.end_headers()
        elif self.path.endswith('.m3u'):
            self.generate_m3u()
        else:
            self.generate_xml()

    def generate_xml(self):
        try:
            bible = requests.get(f"{BIBLE_URL}?t={int(time.time())}", timeout=10).json()
        except: bible = []

        now_utc = datetime.utcnow()
        events_found = []
        seen_matches = set()
        
        # 1. ANALYSE DU FEED ESPN
        leagues = [("hockey","nhl"), ("baseball","mlb"), ("soccer","usa.1")]
        for day in range(3):
            d_str = (now_utc + timedelta(days=day)).strftime("%Y%m%d")
            for sport, league in leagues:
                try:
                    res = requests.get(f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard?dates={d_str}", timeout=5).json()
                    for ev in res.get('events', []):
                        ev_name = ev.get('name', '').upper()
                        if ev_name in seen_matches: continue
                        
                        ev_time = datetime.strptime(ev.get('date'), "%Y-%m-%dT%H:%MZ")
                        
                        # Recherche ultra-permissive dans la bible
                        # On prend les mots de plus de 4 lettres du match ESPN
                        keywords = [t for t in ev_name.replace(' AT ',' ').replace(' @ ',' ').split(' ') if len(t) > 4]
                        
                        best_match = None
                        for p in bible:
                            # Parsing robuste du temps (ignore tout après le premier espace)
                            p_start_str = p['start'].split(' ')[0][:14]
                            p_start = datetime.strptime(p_start_str, "%Y%m%d%H%M%S")
                            
                            # Si le match est le même jour (fenêtre de 6h pour couvrir les avant-matchs)
                            if abs((ev_time - p_start).total_seconds()) < 21600:
                                # Si un des mots clés ESPN est dans le titre de l'EPG
                                if any(k in p['title'].upper() or k in p['desc'].upper() for k in keywords):
                                    best_match = p
                                    break
                        
                        if best_match:
                            events_found.append({
                                "title": ev_name,
                                "score": get_match_score(ev_name),
                                "start": best_match['start'].split(' ')[0][:14],
                                "stop": best_match['stop'].split(' ')[0][:14],
                                "ch_name": CH_NAMES.get(best_match['ch'], "TV")
                            })
                            seen_matches.add(ev_name)
                except: continue

        # 2. ALGORITHME D'EMPILAGE (Priorité 1 -> Canal 1)
        events_found.sort(key=lambda x: x['score'], reverse=True)
        channels = {i: [] for i in range(1, 6)}
        
        for ev in events_found:
            for i in range(1, 6):
                has_collision = False
                for existing in channels[i]:
                    if not (ev['stop'] <= existing['start'] or ev['start'] >= existing['stop']):
                        has_collision = True
                        break
                if not has_collision:
                    channels[i].append(ev)
                    break

        # 3. GÉNÉRATION DU XML
        self.send_response(200)
        self.send_header('Content-type', 'application/xml; charset=utf-8')
        self.end_headers()
        
        xml = '<?xml version="1.0" encoding="UTF-8"?><tv>'
        for i in range(1, 6):
            xml += f'<channel id="CHOIX.{i}"><display-name>CHOIX {i}</display-name></channel>'
            # Tri chronologique pour l'affichage
            progs = sorted(channels[i], key=lambda x: x['start'])
            cursor = (now_utc - timedelta(hours=6)).strftime("%Y%m%d%H%M%S")
            
            for p in progs:
                # Remplissage des trous
                if p['start'] > cursor:
                    xml += f'<programme start="{cursor} +0000" stop="{p["start"]} +0000" channel="CHOIX.{i}"><title>Prochainement: {p["title"].replace("&", "&amp;")}</title></programme>'
                
                xml += f'<programme start="{p["start"]} +0000" stop="{p["stop"]} +0000" channel="CHOIX.{i}">'
                xml += f'<title>{p["title"].replace("&", "&amp;")} [{p["ch_name"]}]</title></programme>'
                cursor = p['stop']
            
            # Fin de grille
            end = (now_utc + timedelta(days=2)).strftime("%Y%m%d%H%M%S")
            if cursor < end:
                xml += f'<programme start="{cursor} +0000" stop="{end} +0000" channel="CHOIX.{i}"><title>🌙 Fin des émissions</title></programme>'

        self.wfile.write((xml + '</tv>').encode('utf-8'))

    def generate_m3u(self):
        host = self.headers.get('Host')
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        m3u = "#EXTM3U\n"
        for i in range(1, 6):
            m3u += f'#EXTINF:-1 tvg-id="CHOIX.{i}" group-title="REGIE",CHOIX {i}\nhttp://{host}/api/stream/{i}\n'
        self.wfile.write(m3u.encode('utf-8'))
        
