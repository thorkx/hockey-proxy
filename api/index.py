from http.server import BaseHTTPRequestHandler
import requests
import json
import re
from datetime import datetime, timedelta

JSON_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

# Équivalences strictes (Vérifie que ces IDs sont exactement ceux dans ton JSON GitHub)
EQUIVALENCE = {
    "I123.15676.schedulesdirect.org": "184813", # RDS 1
    "I124.39080.schedulesdirect.org": "184814", # RDS 2
    "I111.15670.schedulesdirect.org": "184816", # TSN 1
    "I154.58314.schedulesdirect.org": "184821", # TVA Sports
    "I428.49882.gracenote.com": "71518",        # Sportsnet East
    "I432.49886.gracenote.com": "71522",        # Sportsnet One
    "I1000.49609.schedulesdirect.org": "176800",# Sky Main Event
    "I1001.104327.schedulesdirect.org": "176801" # Sky Football
}

PRIORITIES = ["CANADIENS", "MONTRÉAL", "PSG", "CITY", "F1", "EFL", "LIVE"]

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 1. Récupération des données
        events = []
        try:
            r = requests.get(JSON_URL, timeout=5)
            match = re.search(r'\[.*\]', r.text, re.DOTALL)
            if match:
                events = json.loads(match.group(0))
        except: pass

        # 2. Filtrage et tri par priorité
        found_matches = []
        for ev in events:
            title = ev.get('title', '').upper()
            ch_id = ev.get('ch', '')
            if ch_id in EQUIVALENCE:
                score = 99
                for i, team in enumerate(PRIORITIES):
                    if team in title:
                        score = i
                        break
                found_matches.append({
                    'title': ev.get('title'),
                    'stream_id': EQUIVALENCE[ch_id],
                    'start': ev.get('start'),
                    'score': score
                })
        
        found_matches.sort(key=lambda x: x['score'])

        # --- MODE XML (EPG) ---
        if "type=xml" in self.path:
            self.send_response(200)
            self.send_header('Content-type', 'application/xml; charset=utf-8')
            self.end_headers()
            
            xml = '<?xml version="1.0" encoding="UTF-8"?>\n<tv generator-info-name="CustomEPG">'
            for i in range(1, 6):
                xml += f'\n  <channel id="CHOIX.{i}"><display-name>CHOIX {i}</display-name></channel>'
                
                if (i-1) < len(found_matches):
                    m = found_matches[i-1]
                    # Nettoyage du temps : on veut YYYYMMDDHHMMSS +0000
                    raw_start = m['start'].replace(" ", "").replace("+0000", "")
                    start_formatted = f"{raw_start} +0000"
                    
                    # On crée une heure de fin (+3h)
                    try:
                        dt_start = datetime.strptime(raw_start[:14], "%Y%m%d%H%M%S")
                        stop_formatted = (dt_start + timedelta(hours=3)).strftime("%Y%m%d%H%M%S") + " +0000"
                    except:
                        stop_formatted = start_formatted

                    xml += f'\n  <programme start="{start_formatted}" stop="{stop_formatted}" channel="CHOIX.{i}">'
                    xml += f'\n    <title lang="fr">{m["title"]}</title>'
                    xml += f'\n    <desc lang="fr">Match prioritaire sélectionné automatiquement.</desc>'
                    xml += f'\n  </programme>'
            
            xml += '\n</tv>'
            self.wfile.write(xml.encode('utf-8'))

        # --- MODE M3U (PLAYLIST) ---
        else:
            self.send_response(200)
            self.send_header('Content-type', 'audio/x-mpegurl; charset=utf-8')
            self.end_headers()
            
            host = self.headers.get('Host')
            # L'URL de l'EPG doit être accessible par l'app
            epg_url = f"https://{host}/api?type=xml"
            
            playlist = f'#EXTM3U x-tvg-url="{epg_url}"\n'
            for i in range(1, 6):
                if (i-1) < len(found_matches):
                    m = found_matches[i-1]
                    # IMPORTANT: tvg-id doit être IDENTIQUE à l'id du channel dans le XML
                    playlist += f'#EXTINF:-1 tvg-id="CHOIX.{i}" tvg-name="CHOIX {i}", CHOIX {i} : {m["title"]}\n'
                    playlist += f'{STREAM_BASE}/{m['stream_id']}\n'
                else:
                    playlist += f'#EXTINF:-1 tvg-id="CHOIX.{i}", CHOIX {i} (Aucun match)\n'
                    playlist += f'http://0.0.0.0\n'
            
            self.wfile.write(playlist.encode('utf-8'))
            
