from http.server import BaseHTTPRequestHandler
import requests
import json
import time
from datetime import datetime, timedelta

# --- CONFIGURATION DES PRIORITÉS ---
# L'ordre est important : on place les exceptions AVANT les scores de base des ligues.
RULES = [
    # PRIORITÉ ABSOLUE (Habs)
    ({"league": "nhl", "keywords": ["CANADIENS", "MONTREAL", "HABS"]}, 1000),
    
    # SOCCER (CF Montréal / Impact)
    ({"league": "usa.1", "keywords": ["MONTREAL", "IMPACT"]}, 900),
    
    # BASEBALL (Blue Jays)
    ({"league": "mlb", "keywords": ["BLUE JAYS", "TORONTO"]}, 800),

    # BASKETBALL (Raptors)
    ({"league": "nba", "keywords": ["RAPTORS"]}, 700),
    
    # LES RIVAUX (Maple Leafs - On les descend au hockey seulement)
    ({"league": "nhl", "keywords": ["MAPLE LEAFS", "TORONTO"]}, -500),
    
    # SCORE DE BASE PAR LIGUE (Si aucune règle spécifique ne match)
    ({"league": "nhl", "keywords": []}, 500),
    ({"league": "mlb", "keywords": []}, 300),
    ({"league": "nba", "keywords": []}, 200),
    ({"league": "usa.1", "keywords": []}, 150),
    ({"league": "eng.1", "keywords": []}, 100),
]

# DURÉES DÉDIÉES PAR SPORT (en minutes)
SPORT_DURATIONS = {
    "hockey": 165,    # 2h45
    "baseball": 180,  # 3h
    "basketball": 150,# 2h30
    "soccer": 120,    # 2h
    "f1": 135         # 2h15
}

BIBLE_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

CH_NAMES = {
    "I123.15676.schedulesdirect.org": "RDS", 
    "I124.15677.schedulesdirect.org": "RDS 2",
    "I154.58314.schedulesdirect.org": "TVA Sports", 
    "I155.58315.schedulesdirect.org": "TVA Sports 2",
    "I111.15670.schedulesdirect.org": "TSN 1",
    "I112.15671.schedulesdirect.org": "TSN 2"
}

def calculate_score(ev_name, league_key):
    name = ev_name.upper()
    final_score = 0
    match_found = False
    
    for criteria, score in RULES:
        if criteria["league"] == league_key:
            # Si la règle a des mots-clés, on vérifie s'ils sont présents
            if criteria["keywords"]:
                if any(k in name for k in criteria["keywords"]):
                    return score # Match spécifique trouvé (ex: Canadiens ou Raptors)
            else:
                # Sinon, on garde le score de base de la ligue si rien d'autre n'a matché
                if not match_found:
                    final_score = score
                    match_found = True
    return final_score

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if "/stream/" in self.path:
            self.send_response(302)
            self.send_header('Location', f"{STREAM_BASE}/71151")
            self.end_headers()
        elif self.path.endswith('.m3u'):
            self.generate_m3u()
        else:
            self.generate_xml()

    def generate_xml(self):
        try:
            # Ajout d'un timestamp pour éviter le cache GitHub
            bible = requests.get(f"{BIBLE_URL}?t={int(time.time())}", timeout=10).json()
        except: 
            bible = []

        now_utc = datetime.utcnow()
        events_to_stack = []
        seen_matches = set()
        
        # Liste des ligues à scanner sur ESPN
        leagues_to_track = [
            ("hockey", "nhl"), ("baseball", "mlb"), 
            ("basketball", "nba"), ("soccer", "usa.1"),
            ("soccer", "eng.1")
        ]
        
        for day in range(3):
            d_str = (now_utc + timedelta(days=day)).strftime("%Y%m%d")
            for sport, league in leagues_to_track:
                try:
                    res = requests.get(f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard?dates={d_str}", timeout=5).json()
                    for ev in res.get('events', []):
                        ev_name = ev.get('name', '').upper()
                        if ev_name in seen_matches: continue
                        
                        # SOURCE DE VÉRITÉ : ESPN
                        start_dt = datetime.strptime(ev.get('date'), "%Y-%m-%dT%H:%MZ")
                        duration = SPORT_DURATIONS.get(sport, 150)
                        stop_dt = start_dt + timedelta(minutes=duration)
                        
                        # CONCORDANCE AVEC LA BIBLE (Recherche large)
                        keywords = [t for t in ev_name.replace(' AT ',' ').replace(' @ ',' ').split(' ') if len(t) > 4]
                        confirmed_ch = None
                        for p in bible:
                            p_start = datetime.strptime(p['start'].split(' ')[0][:14], "%Y%m%d%H%M%S")
                            if abs((start_dt - p_start).total_seconds()) < 14400: # Fenêtre de 4h
                                if any(k in p['title'].upper() for k in keywords):
                                    confirmed_ch = CH_NAMES.get(p['ch'], "TV")
                                    break
                        
                        if confirmed_ch:
                            events_to_stack.append({
                                "title": ev_name,
                                "score": calculate_score(ev_name, league),
                                "start": start_dt.strftime("%Y%m%d%H%M%S"),
                                "stop": stop_dt.strftime("%Y%m%d%H%M%S"),
                                "ch_name": confirmed_ch
                            })
                            seen_matches.add(ev_name)
                except: continue

        # --- ALGORITHME D'EMPILAGE ---
        # 1. Trier tous les matchs trouvés par score (décroissant)
        events_to_stack.sort(key=lambda x: x['score'], reverse=True)
        
        channels = {i: [] for i in range(1, 6)}
        
        # 2. Placer chaque match sur le premier canal disponible (1 à 5)
        for ev in events_to_stack:
            for i in range(1, 6):
                collision = False
                for existing in channels[i]:
                    if not (ev['stop'] <= existing['start'] or ev['start'] >= existing['stop']):
                        collision = True
                        break
                if not collision:
                    channels[i].append(ev)
                    break

        # --- GÉNÉRATION XML ---
        self.send_response(200)
        self.send_header('Content-type', 'application/xml; charset=utf-8')
        self.end_headers()
        
        xml = '<?xml version="1.0" encoding="UTF-8"?><tv>'
        for i in range(1, 6):
            xml += f'<channel id="CHOIX.{i}"><display-name>CHOIX {i}</display-name></channel>'
            progs = sorted(channels[i], key=lambda x: x['start'])
            
            # Début du guide 6h avant l'heure actuelle
            cursor = (now_utc - timedelta(hours=6)).strftime("%Y%m%d%H%M%S")
            
            for p in progs:
                if p['start'] > cursor:
                    xml += f'<programme start="{cursor} +0000" stop="{p["start"]} +0000" channel="CHOIX.{i}"><title>Prochainement: {p["title"]}</title></programme>'
                
                xml += f'<programme start="{p["start"]} +0000" stop="{p["stop"]} +0000" channel="CHOIX.{i}">'
                xml += f'<title>{p["title"]} [{p["ch_name"]}]</title></programme>'
                cursor = p['stop']
            
            # Fin du guide
            end_limit = (now_utc + timedelta(days=2)).strftime("%Y%m%d%H%M%S")
            if cursor < end_limit:
                xml += f'<programme start="{cursor} +0000" stop="{end_limit} +0000" channel="CHOIX.{i}"><title>🌙 Fin des émissions</title></programme>'

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
        
