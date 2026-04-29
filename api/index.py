from http.server import BaseHTTPRequestHandler
import requests
from datetime import datetime
import json

# --- CONFIGURATION ---
JSON_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

# --- TES PRIORITÉS ---
TOP_TEAMS = ["CANADIENS", "CF MONTRÉAL", "BLUE JAYS", "RAPTORS", "MANCHESTER CITY", "PSG", "BOLOGNE", "WREXHAM", "F1", "LEWIS HAMILTON"]
SECONDARY_TEAMS = ["AVALANCHE", "SABRES", "UTAH HOCKEY", "OILERS", "LAKERS", "WARRIORS", "CELTICS", "YANKEES", "DODGERS", "INTER MIAMI"]

# --- DICTIONNAIRE DE CORRESPONDANCE GLOBAL ---
CH_LINKS = {
    # --- QUÉBEC & CANADA ---
    "I123.15676.schedulesdirect.org": "184813",  # RDS FHD
    "I124.39080.schedulesdirect.org": "184814",  # RDS 2 FHD
    "I125.15678.schedulesdirect.org": "70935",   # RDS INFO
    "I154.58314.schedulesdirect.org": "184821",  # TVA SPORTS FHD
    "I155.58315.schedulesdirect.org": "184822",  # TVA SPORTS 2 FHD
    "I111.15670.schedulesdirect.org": "184816",  # TSN 1
    "I112.15671.schedulesdirect.org": "184817",  # TSN 2
    "I113.15672.schedulesdirect.org": "184818",  # TSN 3
    "I114.15673.schedulesdirect.org": "184819",  # TSN 4
    "I115.15674.schedulesdirect.org": "184820",  # TSN 5

    # --- DAZN (FULL PACK) ---
    "DAZN1": "176814", "DAZN2": "176815", "DAZN3": "176816", 
    "DAZN4": "176817", "DAZN5": "176818", "DAZN6": "176819",
    "DAZN7": "176820", "DAZN8": "176821", "DAZN9": "176822", 
    "DAZN10": "176823",

    # --- APPLE MLS SEASON PASS (FULL FEEDS) ---
    # Mappés sur les flux événementiels de ta playlist
    "MLS1": "176901", "MLS2": "176902", "MLS3": "176903", "MLS4": "176904",
    "MLS5": "176905", "MLS6": "176906", "MLS7": "176907", "MLS8": "176908",
    "MLS9": "176909", "MLS10": "176910", "MLS11": "176911", "MLS12": "176912",
    "MLS13": "176913", "MLS14": "176914", "MLS15": "176915",

    # --- FOOT EUROPÉEN ---
    "I1000.49609.schedulesdirect.org": "176800", # Sky Main Event
    "I1001.104327.schedulesdirect.org": "176801",# Sky Football
    "I50001.schedulesdirect.org": "50001",       # CANAL+
    "I50003.schedulesdirect.org": "50003",       # CANAL+ FOOT
    "I392.76942.gracenote.com": "157279",        # beIN 1
}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'audio/x-mpegurl')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        try:
            r = requests.get(JSON_URL, timeout=10)
            epg_data = r.json()
        except:
            epg_data = []

        playlist = "#EXTM3U\n"
        added_ids = set()

        # 1. SECTION FAVORIS : Scan intelligent
        playlist += "\n# --- MATCHS PRIORITAIRES ---\n"
        for team in TOP_TEAMS + SECONDARY_TEAMS:
            for prog in epg_data:
                title = prog.get('title', '').upper()
                name = prog.get('name', '').upper()
                ch_id = prog.get('ch')
                
                # Détection automatique : si le titre contient l'équipe OU 
                # si c'est un flux MLS/DAZN et que l'équipe joue
                is_match = team in title
                is_special_feed = any(x in name for x in ["MLS", "DAZN", "APPLE"]) and team in title
                
                if (is_match or is_special_feed) and ch_id in CH_LINKS:
                    if ch_id not in added_ids:
                        prefix = "⭐" if team in TOP_TEAMS else "✅"
                        playlist += f'#EXTINF:-1, [{prefix}] {prog["name"]} - {prog["title"]}\n'
                        playlist += f'{STREAM_BASE}/{CH_LINKS[ch_id]}\n'
                        added_ids.add(ch_id)

        # 2. SECTION COMPLÈTE : Tous les feeds sportifs
        playlist += "\n# --- TOUTES LES CHAÎNES SPORT ---\n"
        # On trie pour avoir une liste propre
        for ch_key in sorted(CH_LINKS.keys()):
            stream_id = CH_LINKS[ch_key]
            if ch_key not in added_ids:
                # Cherche le nom propre dans l'EPG, sinon utilise la clé
                ch_display_name = next((p['name'] for p in epg_data if p['ch'] == ch_key), ch_key)
                playlist += f'#EXTINF:-1, {ch_display_name}\n'
                playlist += f'{STREAM_BASE}/{stream_id}\n'

        self.wfile.write(playlist.encode('utf-8'))
        
