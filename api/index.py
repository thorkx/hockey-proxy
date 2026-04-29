from http.server import BaseHTTPRequestHandler
import requests
import json

GITHUB_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            # Récupération brute
            r = requests.get(GITHUB_URL, timeout=10)
            data = r.json()
            
            # On prend le premier item pour le test
            item = data[0] if data else {"title": "JSON VIDE", "start": "20260430030000", "stop": "20260430060000"}
            
            self.send_response(200)
            self.send_header('Content-type', 'application/xml; charset=utf-8')
            self.end_headers()

            # Construction manuelle du XML minimal
            xml = '<?xml version="1.0" encoding="UTF-8"?>\n<tv>\n'
            xml += '  <channel id="CHOIX.1"><display-name>TEST CANAL</display-name></channel>\n'
            
            # Nettoyage rapide des dates pour le format XMLTV
            s = item.get('start', '').replace(" ", "")[:14]
            t = item.get('stop', '').replace(" ", "")[:14]
            
            xml += f'  <programme start="{s} +0000" stop="{t} +0000" channel="CHOIX.1">\n'
            xml += f'    <title lang="fr">{item.get("title")}</title>\n'
            xml += f'  </programme>\n'
            xml += '</tv>'
            
            self.wfile.write(xml.encode('utf-8'))
            
        except Exception as e:
            self.send_response(500)
            self.wfile.write(f"Erreur de parsing: {str(e)}".encode())
            
