from http.server import BaseHTTPRequestHandler
import requests
import json
import re

# Configuration
JSON_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

# Équipes à surveiller
TEAMS = ["CANADIENS", "MONTRÉAL", "BLUE JAYS", "RAPTORS", "CITY", "PSG", "F1", "MIAMI"]

# Mapping de tes chaînes (basé sur ta playlist)
CH_LINKS = {
    "I123.15676.schedulesdirect.org": "184813", # RDS FHD
    "I124.39080.schedulesdirect.org": "184814", # RDS 2 FHD
    "I154.58314.schedulesdirect.org": "184821", # TVA SPORTS FHD
    "I111.15670.schedulesdirect.org": "184816", # TSN 1 FHD
    "I428.49882.gracenote.com": "71518",        # Sportsnet
    "I1000.49609.schedulesdirect.org": "176800" # Sky Main Event
}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'audio/x-mpegurl; charset=utf-8')
        self.end_headers()

        epg_data = []
        
        try:
            # 1. On récupère le texte brut de GitHub
            r = requests.get(JSON_URL, timeout=10)
            raw_content = r.text
            
            # 2. NETTOYAGE AGRESSIF : On cherche tout ce qui est entre le PREMIER [ et le DERNIER ]
            # Ça élimine les ```json ou les messages texte autour du JSON
            json_match = re.search(r'(\[.*\])', raw_content, re.DOTALL)
            
            if json_match:
                # On extrait uniquement la partie JSON trouvée
                json_string = json_match.group(1)
                epg_data = json.loads(json_string)
            else:
                # Si on ne trouve pas de [ ], on essaie de charger le texte brut quand même
                epg_data = json.loads(raw_content)
        except Exception as e:
            # Si ça plante encore, on crée un faux programme pour afficher l'erreur en direct
            epg_data = [{"ch": "ERROR", "title": f"ERREUR JSON: {str(e)}", "name": "DEBUG"}]

        playlist = "#EXTM3U\n"
        added = set()
        priority_lines = ""
        normal_lines = ""

        # 3. Traitement des données
        for prog in epg_data:
            ch_id = prog.get('ch')
            title = prog.get('title', '').upper()
            
            if ch_id in CH_LINKS:
                stream_id = CH_LINKS[ch_id]
                link = f"{STREAM_BASE}/{stream_id}"
                
                # Priorité : Si une de tes équipes est dans le titre
                if any(team in title for team in TEAMS) and ch_id not in added:
                    priority_lines += f'#EXTINF:-1, ⭐ {title}\n{link}\n'
                    added.add(ch_id)
            
            # Cas spécial pour afficher l'erreur dans la liste si le chargement a raté
            elif ch_id == "ERROR":
                playlist += f'#EXTINF:-1, !!! {prog["title"]} !!!\n[http://0.0.0.0](http://0.0.0.0)\n'

        # 4. On ajoute le reste des chaînes mappées pour ne pas avoir une liste vide
        for ch_id, stream_id in CH_LINKS.items():
            if ch_id not in added:
                normal_lines += f'#EXTINF:-1, Poste {ch_id}\n{STREAM_BASE}/{stream_id}\n'

        output = playlist + priority_lines + normal_lines
        self.wfile.write(output.encode('utf-8'))
        
