from http.server import BaseHTTPRequestHandler
import requests
import json
import re
from datetime import datetime, timedelta

# --- CONFIGURATION ---
JSON_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

# ÉQUIVALENCE : Assure-toi que ces IDs sont EXACTEMENT ceux écrits par ton bot
MAP = {
    "I123.15676.schedulesdirect.org": "184813", # RDS 1
    "I124.39080.schedulesdirect.org": "184814", # RDS 2
    "I111.15670.schedulesdirect.org": "184816", # TSN 1
    "I154.58314.schedulesdirect.org": "184821", # TVA Sports
    "I428.49882.gracenote.com": "71518",        # SN East
    "I432.49886.gracenote.com": "71522",        # SN One
    "I1000.49609.schedulesdirect.org": "176800",# Sky Main
}

PRIORITIES = ["CANADIENS", "MONTRÉAL", "PSG", "CITY", "F1", "EFL", "LIVE"]

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 1. Récupération brute et nettoyage du JSON
        events = []
        try:
            r = requests.get(JSON_URL, timeout=5)
            # On cherche le contenu entre crochets [ ] au cas où ton bot ajoute du texte autour
            content = re.search(r'\[.*\]', r.text, re.DOTALL)
            if content:
                events = json.loads(content.group(0))
        except Exception as e:
            print(f"Erreur JSON: {e}")

        # 2. Matching et Scoring
        matches = []
        for e in events:
            # On strip pour éviter les espaces invisibles qui font échouer le dictionnaire
            ch_id = e.get('ch', '').strip()
            if ch_id in MAP:
                title = e.get('title', 'Match inconnu').upper()
                # Score de 0 (top) à 99
                score = 99
                for i, team in enumerate(PRIORITIES):
                    if team in title:
                        score = i
                        break
                matches.append({
                    'title': e.get('title'),
                    'sid': MAP[ch_id],
                    'start': e.get('start', '').replace(" ", ""),
                    'score': score
                })
        
        # Tri par priorité
        matches.sort(key=lambda x: x['score'])

        # --- SORTIE XMLTV (EPG) ---
        if "type=xml" in self.path:
            self.send_response(200)
            self.send_header('Content-type', 'application/xml; charset=utf-8')
            self.end_headers()
            
            xml = '<?xml version="1.0" encoding="UTF-8"?>\n<tv>\n'
            for i in range(1, 6):
                xml += f'  <channel id="CHOIX.{i}"><display-name>CHOIX {i}</display-name></channel>\n'
                
                if (i-1) < len(matches):
                    m = matches[i-1]
                    # Formatage date ultra-strict: YYYYMMDDHHMMSS +0000
                    # On s'assure d'avoir au moins 14 caractères pour le timestamp
                    t = m['start'][:14].ljust(14, '0')
                    start = f"{t} +0000"
                    
                    # Fin à +4h pour être large sur l'EPG
                    try:
                        dt_stop = datetime.strptime(t, "%Y%m%d%H%M%S") + timedelta(hours=4)
                        stop = dt_stop.strftime("%Y%m%d%H%M%S") + " +0000"
                    except:
                        stop = start

                    xml += f'  <programme start="{start}" stop="{stop}" channel="CHOIX.{i}">\n'
                    xml += f'    <title lang="fr">{m["title"]}</title>\n'
                    xml += f'  </programme>\n'
            xml += '</tv>'
            self.wfile.write(xml.encode('utf-8'))

        # --- SORTIE M3U ---
        else:
            self.send_response(200)
            self.send_header('Content-type', 'audio/x-mpegurl; charset=utf-8')
            self.end_headers()
            
            host = self.headers.get('Host')
            # L'URL de l'EPG pointant vers ce même script
            epg_url = f"https://{host}/api?type=xml"
            
            playlist = f'#EXTM3U x-tvg-url="{epg_url}"\n'
            for i in range(1, 6):
                if (i-1) < len(matches):
                    m = matches[i-1]
                    # tvg-id="CHOIX.X" est le lien vital avec le XML
                    playlist += f'#EXTINF:-1 tvg-id="CHOIX.{i}" tvg-name="CHOIX {i}", ⭐ {m["title"]}\n'
                    playlist += f'{STREAM_BASE}/{m["sid"]}\n'
                else:
                    playlist += f'#EXTINF:-1 tvg-id="CHOIX.{i}", CHOIX {i} (Aucun match)\n'
                    playlist += f'http://0.0.0.0\n'
            
            self.wfile.write(playlist.encode('utf-8'))
            
