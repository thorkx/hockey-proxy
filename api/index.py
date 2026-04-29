from http.server import BaseHTTPRequestHandler
import requests
import json
import re

JSON_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

MAP = {
    "I123.15676.schedulesdirect.org": "184813",
    "I124.39080.schedulesdirect.org": "184814",
    "I111.15670.schedulesdirect.org": "184816",
    "I154.58314.schedulesdirect.org": "184821",
    "I1000.49609.schedulesdirect.org": "176800",
    "I1001.104327.schedulesdirect.org": "176801",
    "I446.52300.schedulesdirect.org": "157280",
    "I428.49882.gracenote.com": "71518",
    "I432.49886.gracenote.com": "71522"
}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 1. On tente de lire le JSON coûte que coûte
        events = []
        try:
            r = requests.get(JSON_URL, timeout=10)
            # On logge la réponse brute dans la console Vercel
            print(f"DEBUG BRUT: {r.text[:200]}") 
            data = re.search(r'\[.*\]', r.text, re.DOTALL)
            if data:
                events = json.loads(data.group(0))
        except Exception as e:
            print(f"ERREUR FETCH: {e}")

        # 2. Création de la liste sans calcul de date complexe
        matches = []
        for e in events:
            # Si on a un titre, on le prend
            matches.append({
                'title': e.get('title', 'Sans Titre'),
                'start': e.get('start', '20260428000000').replace(" ", "").replace("+0000", ""),
                'sid': MAP.get(e.get('ch'), "184813") # RDS par défaut si pas dans la MAP
            })

        # --- RÉPONSE XML ---
        if "type=xml" in self.path:
            self.send_response(200)
            self.send_header('Content-type', 'application/xml; charset=utf-8')
            self.end_headers()
            
            xml = '<?xml version="1.0" encoding="UTF-8"?>\n<tv>\n'
            for i in range(1, 6):
                xml += f'  <channel id="CHOIX.{i}"><display-name>CHOIX {i}</display-name></channel>\n'
                
            for i, m in enumerate(matches[:5]):
                ch_id = i + 1
                # Formatage ultra-basique pour éviter les erreurs
                t_start = m['start'].ljust(14, '0')[:14]
                xml += f'  <programme start="{t_start} +0000" stop="{t_start} +0000" channel="CHOIX.{ch_id}">\n'
                xml += f'    <title>{m["title"]}</title>\n'
                xml += f'  </programme>\n'
            
            xml += '</tv>'
            self.wfile.write(xml.encode('utf-8'))

        # --- RÉPONSE M3U ---
        else:
            self.send_response(200)
            self.send_header('Content-type', 'audio/x-mpegurl')
            self.end_headers()
            host = self.headers.get('Host')
            playlist = f'#EXTM3U x-tvg-url="https://{host}/api?type=xml"\n'
            for i in range(1, 6):
                title = matches[i-1]['title'] if (i-1) < len(matches) else "Vide"
                sid = matches[i-1]['sid'] if (i-1) < len(matches) else "184813"
                playlist += f'#EXTINF:-1 tvg-id="CHOIX.{i}", CHOIX {i} ({title})\n'
                playlist += f'{STREAM_BASE}/{sid}\n'
            self.wfile.write(playlist.encode('utf-8'))
            
