from http.server import BaseHTTPRequestHandler
import requests
import json
import re

JSON_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 1. On essaie de chopper le JSON
        events = []
        try:
            r = requests.get(JSON_URL, timeout=10)
            data = re.search(r'\[.*\]', r.text, re.DOTALL)
            if data:
                events = json.loads(data.group(0))
        except:
            pass

        # --- RÉPONSE XML ---
        if "type=xml" in self.path:
            self.send_response(200)
            self.send_header('Content-type', 'application/xml; charset=utf-8')
            self.end_headers()
            
            # Format XMLTV ultra-simplifié
            xml = '<?xml version="1.0" encoding="UTF-8"?>\n<tv>\n'
            for i in range(1, 6):
                xml += f'  <channel id="CHOIX.{i}"><display-name>CHOIX {i}</display-name></channel>\n'
            
            # Si on a des événements, on les affiche. 
            # Sinon, on crée des blocs de texte "TEST" pour voir si l'EPG s'affiche.
            source = events if events else [{"title": "MATCH TEST", "start": "20260428200000"}] * 5

            for i, e in enumerate(source[:5]):
                ch_num = i + 1
                title = e.get('title', 'Sans Titre')
                # On force une date fixe de 24h pour être sûr que ça tombe "pendant" maintenant
                start = "20260428000000 +0000"
                stop = "20260429000000 +0000"
                
                xml += f'  <programme start="{start}" stop="{stop}" channel="CHOIX.{ch_num}">\n'
                xml += f'    <title lang="fr">{title}</title>\n'
                xml += f'    <desc lang="fr">Vérification de la connexion EPG</desc>\n'
                xml += f'  </programme>\n'
            
            xml += '</tv>'
            self.wfile.write(xml.encode('utf-8'))

        # --- RÉPONSE M3U ---
        else:
            self.send_response(200)
            self.send_header('Content-type', 'audio/x-mpegurl')
            self.end_headers()
            host = self.headers.get('Host')
            # On force le tvg-id pour matcher le XML
            playlist = f'#EXTM3U x-tvg-url="https://{host}/api?type=xml"\n'
            for i in range(1, 6):
                playlist += f'#EXTINF:-1 tvg-id="CHOIX.{i}", CHOIX {i}\n'
                playlist += f'{STREAM_BASE}/184813\n' # RDS par défaut
            self.wfile.write(playlist.encode('utf-8'))
            
