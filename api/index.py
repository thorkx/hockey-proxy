from http.server import BaseHTTPRequestHandler
import requests
import json
from datetime import datetime

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Configuration
        GITHUB_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
        
        # 1. Essayer de charger le JSON, sinon créer une liste de secours
        try:
            r = requests.get(GITHUB_URL, timeout=5)
            data = r.json()
        except:
            # Match de secours si GitHub crash (23h MTL = 03h00 UTC le 29 avril)
            data = [{
                "title": "MATCH TEST 23H00 (BACKUP)",
                "start": "20260429030000 +0000",
                "stop": "20260429060000 +0000"
            }]

        # 2. Préparer le XML
        self.send_response(200)
        self.send_header('Content-type', 'application/xml; charset=utf-8')
        self.end_headers()

        xml = '<?xml version="1.0" encoding="UTF-8"?>\n<tv>\n'
        xml += '  <channel id="CHOIX.1"><display-name>CHOIX 1</display-name></channel>\n'

        for item in data:
            # Nettoyage des dates (on enlève les espaces pour le format start/stop)
            s = item.get('start', '20260429030000').replace(" ", "")[:14]
            t = item.get('stop', '20260429060000').replace(" ", "")[:14]
            title = item.get('title', 'Match')

            xml += f'  <programme start="{s} +0000" stop="{t} +0000" channel="CHOIX.1">\n'
            xml += f'    <title lang="fr">{title}</title>\n'
            xml += '  </programme>\n'

        xml += '</tv>'
        self.wfile.write(xml.encode('utf-8'))
        
