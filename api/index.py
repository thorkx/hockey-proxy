from http.server import BaseHTTPRequestHandler
import requests
from datetime import datetime
import json

# --- CONFIGURATION ---
# Assure-toi que ce lien pointe vers ton fichier JSON public sur GitHub
JSON_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

# --- TES PRIORITÉS ---
TOP_TEAMS = ["CANADIENS", "CF MONTRÉAL", "BLUE JAYS", "RAPTORS", "MANCHESTER CITY", "PSG", "BOLOGNE", "WREXHAM", "F1", "LEWIS HAMILTON"]
SECONDARY_TEAMS = ["AVALANCHE", "SABRES", "UTAH HOCKEY", "OILERS", "LAKERS", "WARRIORS", "CELTICS", "YANKEES", "DODGERS", "INTER MIAMI"]

# --- DICTIONNAIRE DE CORRESPONDANCE ---
CH_LINKS = {
    # Québec & Canada
    "I123.15676.schedulesdirect.org": "184813", "I124.39080.schedulesdirect.org": "184814",
    "I125.15678.schedulesdirect.org": "70935", "I154.58314.schedulesdirect.org": "184821",
    "I155.58315.schedulesdirect.org": "184822", "I111.15670.schedulesdirect.org": "184816",
    "I112.15671.schedulesdirect.org": "184817", "I113.15672.schedulesdirect.org": "184818",
    "I114.15673.schedulesdirect.org": "184819", "I115.15674.schedulesdirect.org": "184820",
    # Foot Europe & USA
    "I1000.49609.schedulesdirect.org": "176800", "I1001.104327.schedulesdirect.org": "176801",
    "I50001.schedulesdirect.org": "50001", "I50003.schedulesdirect.org": "50003",
    "I392.76942.gracenote.com": "157279", "I204.12444.schedulesdirect.org": "71444",
    # DAZN & Apple MLS (On ajoute les principaux pour l'exemple)
    "DAZN1": "176814", "DAZN2": "176815", "MLS1": "176901", "MLS2": "176902"
}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'audio/x-mpegurl')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        # 1. Récupération des données du bot GitHub
        epg_data = []
        try:
            r = requests.get(JSON_URL, timeout=10)
            if r.status_code == 200:
                epg_data = r.json()
        except:
            pass

        # 2. Heure actuelle (Format XMLTV: 20260428203000)
        now = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        
        playlist = "#EXTM3U\n"
        added_channels = set()
        priority_content = []

        # 3. ANALYSE DES MATCHS EN DIRECT
        # On cherche dans le JSON ce qui joue MAINTENANT
        for prog in epg_data:
            title = prog.get('title', '').upper()
            ch_id = prog.get('ch')
            start_time = prog.get('start', '').split(' ')[0] # On garde juste les chiffres

            # On vérifie si c'est une de tes équipes ET si ça joue en ce moment (ou commence bientôt)
            is_priority = any(team in title for team in TOP_TEAMS + SECONDARY_TEAMS)
            
            if is_priority and ch_id in CH_LINKS:
                # Si le match a commencé ou commence dans les 15 prochaines minutes
                if start_time <= now: 
                    prefix = "⭐" if any(t in title for t in TOP_TEAMS) else "✅"
                    priority_content.append(f'#EXTINF:-1, {prefix} LIVE: {prog["name"]} - {prog["title"]}\n{STREAM_BASE}/{CH_LINKS[ch_id]}')
                    added_channels.add(ch_id)

        # 4. CONSTRUCTION DE LA PLAYLIST
        # On met les matchs en direct tout en haut
        if priority_content:
            playlist += "\n# --- MATCHS EN COURS ---\n"
            playlist += "\n".join(priority_content) + "\n"

        # On ajoute le reste des chaînes sportives pour le zapping
        playlist += "\n# --- TOUTES LES CHAÎNES ---\n"
        for ch_id, stream_id in CH_LINKS.items():
            if ch_id not in added_channels:
                # On essaie de trouver le nom de l'émission actuelle pour chaque chaîne
                current_show = next((p['title'] for p in epg_data if p['ch'] == ch_id and p.get('start', '').split(' ')[0] <= now), "Sport")
                ch_name = next((p['name'] for p in epg_data if p['ch'] == ch_id), ch_id)
                
                playlist += f'#EXTINF:-1, {ch_name} - {current_show}\n'
                playlist += f'{STREAM_BASE}/{stream_id}\n'

        self.wfile.write(playlist.encode('utf-8'))
        
