from http.server import BaseHTTPRequestHandler
import requests
import json

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # L'URL RAW avec ton nom de repo exact
        # Note: Si ton nom d'utilisateur n'est pas 'thorkx', remplace-le ici.
        URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
        
        self.send_response(200)
        self.send_header('Content-type', 'application/xml; charset=utf-8')
        self.end_headers()

        try:
            # On force GitHub à ne pas nous servir une version cachée (Cache-Control)
            r = requests.get(URL, headers={'Cache-Control': 'no-cache'}, timeout=10)
            
            if r.status_code != 200:
                raise Exception(f"GitHub Error {r.status_code}: Verifie que le fichier est public.")

            data = r.json()
            
            xml = '<?xml version="1.0" encoding="UTF-8"?><tv>'
            # On crée nos 5 canaux virtuels
            for i in range(1, 6):
                xml += f'<channel id="CHOIX.{i}"><display-name>CHOIX {i}</display-name></channel>'
            
            # On boucle sur les données du JSON
            for item in data:
                # Nettoyage des dates pour le XMLTV
                s = item.get('start', '').replace(" ", "")[:14]
                t = item.get('stop', '').replace(" ", "")[:14]
                # Par défaut on met tout sur CHOIX 1 pour ce test de connexion
                xml += f'<programme start="{s} +0000" stop="{t} +0000" channel="CHOIX.1">'
                xml += f'<title lang="fr">{item.get("title")}</title>'
                xml += f'<desc lang="fr">{item.get("desc", "")}</desc>'
                xml += '</programme>'
            
            xml += '</tv>'
            self.wfile.write(xml.encode('utf-8'))

        except Exception as e:
            # Si ça foire, le guide affichera l'erreur
            err_xml = f'<?xml version="1.0" encoding="UTF-8"?><tv>'
            err_xml += f'<channel id="CHOIX.1"><display-name>ERREUR</display-name></channel>'
            err_xml += f'<programme start="20260429000000 +0000" stop="20260429235900 +0000" channel="CHOIX.1">'
            err_xml += f'<title>ERREUR: {str(e)}</title>'
            err_xml += f'</programme></tv>'
            self.wfile.write(err_xml.encode('utf-8'))
            
