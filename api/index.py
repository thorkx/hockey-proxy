from http.server import BaseHTTPRequestHandler
import requests
import json
from datetime import datetime, timedelta

# CONFIGURATION
BIBLE_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

# Dictionnaire des sports et logos
LEAGUES = {
    "hockey": "🏒",
    "baseball": "⚾",
    "soccer": "⚽",
    "basketball": "🏀"
}

# Noms simplifiés pour l'affichage dans le titre
CH_NAMES = {
    "I408.18800.schedulesdirect.org": "SN West",
    "I123.15676.schedulesdirect.org": "RDS",
    "I111.15670.schedulesdirect.org": "TSN",
    "I154.58314.schedulesdirect.org": "TVA Sports",
    "I446.52300.schedulesdirect.org": "Sky MX"
}

# Mapping vers tes flux IPTV réels
STREAM_MAP = {
    "I408.18800.schedulesdirect.org": "71520", # Sportsnet
    "I123.15676.schedulesdirect.org": "184813", # RDS
    "I111.15670.schedulesdirect.org": "184816", # TSN
    "I154.58314.schedulesdirect.org": "184821"  # TVA Sports
}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 1. RÉCUPÉRATION DE LA BIBLE
        try:
            bible = requests.get(BIBLE_URL, headers={'Cache-Control': 'no-cache'}, timeout=10).json()
        except:
            bible = []

        final_selection = []
        now_utc = datetime.utcnow()

        # 2. RÉCUPÉRATION DES MATCHS (4 JOURS)
        for day_offset in range(4):
            target_date = (now_utc + timedelta(days=day_offset)).strftime("%Y%m%d")
            
            for sport, icon in LEAGUES.items():
                # Définition de la ligue selon le sport
                league_id = "nhl" if sport == "hockey" else "mlb" if sport == "baseball" else "eng.1" if sport == "soccer" else "nba"
                url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league_id}/scoreboard?dates={target_date}"
                
                try:
                    res = requests.get(url, timeout=5).json()
                    for event in res.get('events', []):
                        name = event.get('name', '').upper()
                        espn_time = datetime.strptime(event.get('date'), "%Y-%m-%dT%H:%MZ")
                        
                        # --- MATCHMAKING & RECHERCHE DE MULTI-DIFFUSION ---
                        matching_progs = []
                        teams = name.replace(' AT ', ' ').replace(' @ ', ' ').split(' ')
                        clean_teams = [t for t in teams if len(t) > 3]

                        for prog in bible:
                            try:
                                p_start = datetime.strptime(prog.get('start', '')[:14], "%Y%m%d%H%M%S")
                                # Tolérance de 2 heures entre ESPN et ton Bot
                                if abs((espn_time - p_start).total_seconds()) / 3600 <= 2.0:
                                    prog_text = (prog.get('title', '') + " " + prog.get('desc', '')).upper()
                                    if any(t in prog_text for t in clean_teams):
                                        matching_progs.append(prog)
                            except: continue

                        # --- CONSTRUCTION DU TITRE ENRICHI ---
                        if matching_progs:
                            # Stream primaire : on cherche d'abord dans notre STREAM_MAP
                            primary = next((p for p in matching_progs if p['ch'] in STREAM_MAP), matching_progs[0])
                            sid = STREAM_MAP.get(primary['ch'], "184813") # RDS par défaut
                            
                            # DÉDUPLICATION : On nettoie les doublons de noms de chaînes
                            raw_channels = [CH_NAMES.get(p['ch'], p['name']) for p in matching_progs]
                            unique_channels = []
                            for ch in raw_channels:
                                if ch not in unique_channels:
                                    unique_channels.append(ch)
                            
                            ch_info = f"[{' | '.join(unique_channels)}]"
                            title = f"{icon} {event.get('name')} {ch_info}"
                            start, stop = primary['start'][:14], primary['stop'][:14]
                        else:
                            # Mode PRÉVU (Option B)
                            sid = "184813"
                            start = espn_time.strftime("%Y%m%d%H%M%S")
                            stop = (espn_time + timedelta(hours=3)).strftime("%Y%m%d%H%M%S")
                            title = f"{icon} {event.get('name')} [À CONFIRMER]"

                        final_selection.append({
                            "title": title,
                            "sid": sid,
                            "start": start,
                            "stop": stop,
                            "priority": 100 if any(f in name for f in ["CANADIENS", "JAYS", "MTL", "TORONTO"]) else 10
                        })
                except: continue

        # 3. RÉGIE (Distribution sur 5 canaux sans collision)
        final_selection.sort(key=lambda x: x['priority'], reverse=True)
        channels = {i: [] for i in range(1, 6)}
        for m in final_selection:
            for i in range(1, 6):
                collision = any(not (m['stop'] <= ex['start'] or m['start'] >= ex['stop']) for ex in channels[i])
                if not collision:
                    channels[i].append(m)
                    break

        # 4. GÉNÉRATION XMLTV
        self.send_response(200)
        self.send_header('Content-type', 'application/xml; charset=utf-8')
        self.end_headers()
        
        def clean_xml(text):
            if not text: return ""
            return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;")

        xml = '<?xml version="1.0" encoding="UTF-8"?><tv>'
        for i in range(1, 6):
            xml += f'<channel id="CHOIX.{i}"><display-name>CHOIX {i}</display-name></channel>'
            for p in channels[i]:
                safe_title = clean_xml(p['title'])
                xml += f'<programme start="{p["start"]} +0000" stop="{p["stop"]} +0000" channel="CHOIX.{i}">'
                xml += f'<title lang="fr">{safe_title}</title></programme>'
        xml += '</tv>'
        self.wfile.write(xml.encode('utf-8'))
        
