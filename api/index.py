from http.server import BaseHTTPRequestHandler
import requests
import json
import re
from datetime import datetime

# --- CONFIGURATION ---
JSON_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

# Ordre d'importance des équipes/mots-clés
PRIORITY_LIST = ["CANADIENS", "MONTRÉAL", "PSG", "CITY", "F1", "BLUE JAYS", "RAPTORS", "NFL", "LIVE"]

# Mapping ID EPG -> ID Stream IPTV
CH_MAP = {
    "I123.15676.schedulesdirect.org": "184813",  # RDS 1
    "I124.39080.schedulesdirect.org": "184814",  # RDS 2
    "I111.15670.schedulesdirect.org": "184816",  # TSN 1
    "I154.58314.schedulesdirect.org": "184821",  # TVA Sports
    "I1000.49609.schedulesdirect.org": "176800", # Sky Main Event
    "I1001.104327.schedulesdirect.org": "176801",# Sky Football
    "I446.52300.schedulesdirect.org": "157280",  # Sky Mexico
}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # On récupère les données de match
        r = requests.get(JSON_URL, timeout=5)
        content = r.text
        match = re.search(r'\[.*\]', content, re.DOTALL)
        events = json.loads(match.group(0)) if match else []

        # 1. ANALYSE ET TRI PAR PRIORITÉ
        # On crée une liste de matchs "Actifs" qui sont dans notre CH_MAP
        active_matches = []
        for ev in events:
            title = ev.get('title', '').upper()
            ch_id = ev.get('ch', '')
            if ch_id in CH_MAP:
                # On calcule le score de priorité
                score = 999
                for i, team in enumerate(PRIORITY_LIST):
                    if team in title:
                        score = i
                        break
                active_matches.append({'title': ev.get('title'), 'ch': ch_id, 'score': score})

        # On trie par score (le plus bas en premier)
        active_matches.sort(key=lambda x: x['score'])

        # 2. GÉNÉRATION DE LA PLAYLIST DYNAMIQUE
        self.send_response(200)
        self.send_header('Content-type', 'audio/x-mpegurl; charset=utf-8')
        self.end_headers()

        playlist = "#EXTM3U\n"
        
        # On génère les 3 meilleurs choix possibles
        for i in range(3):
            if i < len(active_matches):
                match = active_matches[i]
                stream_id = CH_MAP[match['ch']]
                playlist += f'#EXTINF:-1, [CHOIX {i+1}] ⭐ {match["title"]}\n'
                playlist += f'{STREAM_BASE}/{stream_id}\n'
            else:
                # Si rien ne joue, on met un poste par défaut (ex: RDS pour Choix 1)
                default_ids = ["184813", "184816", "176800"]
                playlist += f'#EXTINF:-1, [CHOIX {i+1}] (Rien en direct)\n'
                playlist += f'{STREAM_BASE}/{default_ids[i]}\n'

        self.wfile.write(playlist.encode('utf-8'))
        
