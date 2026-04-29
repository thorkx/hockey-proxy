from http.server import BaseHTTPRequestHandler
import requests
import json
import time
import re
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

# --- CONFIGURATION ---
BIBLE_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

# --- MAPPAGE COMPLET (FR + EN + UK) ---
CH_DATABASE = {
    # FR
    "I1000.49609.schedulesdirect.org": {"name": "RDS", "id": "184813", "lang": "FR"},
    "I123.15676.schedulesdirect.org": {"name": "RDS", "id": "184813", "lang": "FR"},
    "I124.15677.schedulesdirect.org": {"name": "RDS 2", "id": "184814", "lang": "FR"},
    "I193.73142.schedulesdirect.org": {"name": "TVA Sports", "id": "184811", "lang": "FR"},
    "I154.58314.schedulesdirect.org": {"name": "TVA Sports", "id": "184811", "lang": "FR"},
    
    # EN (CANADA) - Ajout des IDs détectés dans ton XML
    "I405.62111.schedulesdirect.org": {"name": "Sportsnet 4K", "id": "157674", "lang": "EN"},
    "I409.68858.schedulesdirect.org": {"name": "TSN / SN", "id": "71234", "lang": "EN"},
    "SNEast": {"name": "SN East", "id": "71518", "lang": "EN"},
    "SNWest": {"name": "SN West", "id": "71521", "lang": "EN"},
    "SNPacific": {"name": "SN Pacific", "id": "71520", "lang": "EN"},
    "SNOntario": {"name": "SN Ontario", "id": "71519", "lang": "EN"},
    "TSN1": {"name": "TSN 1", "id": "71234", "lang": "EN"},
    "TSN2": {"name": "TSN 2", "id": "71235", "lang": "EN"},
    
    # UK / INT
    "TNT_Sports_1": {"name": "TNT 1", "id": "71151", "lang": "EN"},
    "Sky_Sports_F1": {"name": "Sky F1", "id": "74316", "lang": "EN"},
    "beINSPORTSMAX4.fr": {"name": "beIN MAX 4", "id": "49898", "lang": "FR"}
}

def clean_text(t):
    if not t: return ""
    # Retire accents et caractères spéciaux
    t = re.sub(r'[ÉÈÊË]', 'E', t.upper())
    t = re.sub(r'[ÀÂÄ]', 'A', t)
    return re.sub(r'[^\w\s]', ' ', t)

def find_match_in_bible(ev_name, bible_data, ev_date_str):
    ev_time = datetime.strptime(ev_date_str, "%Y-%m-%dT%H:%MZ")
    # On extrait les noms d'équipes (ex: "CANADIENS", "BLUE", "JAYS")
    teams = [w for w in clean_text(ev_name).split() if len(w) > 3 and w not in ["MONTREAL", "TORONTO"]]
    
    for prog in bible_data:
        try:
            # On gère le format "20260429190700 +0000"
            p_start_str = prog['start'].split(' ')[0]
            p_start = datetime.strptime(p_start_str, "%Y%m%d%H%M%S")
        except: continue

        # Fenêtre de 4h
        if abs((ev_time - p_start).total_seconds()) < 14400:
            search_zone = clean_text(prog.get('title', '')) + " " + clean_text(prog.get('desc', ''))
            if any(team in search_zone for team in teams):
                return prog['ch']
    return None

class handler(BaseHTTPRequestHandler):
    def get_organized_events(self):
        try: 
            bible = requests.get(BIBLE_URL, timeout=5).json()
        except: 
            bible = []
        
        now = datetime.utcnow()
        events = []
        seen = set()

        # Ligues à scanner
        leagues = [("hockey","nhl"), ("basketball","nba"), ("baseball","mlb"), ("soccer","usa.1")]
        
        for sport, lg in leagues:
            try:
                # On scanne aujourd'hui et demain
                for day in range(2):
                    date_str = (now + timedelta(days=day)).strftime("%Y%m%d")
                    url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{lg}/scoreboard?dates={date_str}"
                    data = requests.get(url, timeout=3).json()
                    
                    for ev in data.get('events', []):
                        name = ev['name'].upper()
                        if name in seen: continue
                        
                        ch_key = find_match_in_bible(name, bible, ev['date'])
                        
                        # SCORE DE PRIORITÉ (Sans biais de langue pour le tri)
                        score = 0
                        if any(k in name for k in ["CANADIENS", "RAPTORS", "BLUE JAYS", "CF MONTREAL"]):
                            score += 1000
                        elif lg == "nhl": score += 500
                        elif lg == "mlb": score += 300
                        
                        # Bonus de langue (On garde le FR en haut si dispo, mais on n'exclut pas l'EN)
                        info = CH_DATABASE.get(ch_key, {})
                        if info.get("lang") == "FR": score += 100

                        events.append({
                            "title": name, 
                            "score": score, 
                            "start": datetime.strptime(ev['date'], "%Y-%m-%dT%H:%MZ"), 
                            "stop": datetime.strptime(ev['date'], "%Y-%m-%dT%H:%MZ") + timedelta(hours=3), 
                            "ch_key": ch_key
                        })
                        seen.add(name)
            except: continue

        events.sort(key=lambda x: x['score'], reverse=True)
        chans = {i: [] for i in range(1, 6)}
        for e in events:
            for i in range(1, 6):
                if not any(not (e['stop'] <= ex['start'] or e['start'] >= ex['stop']) for ex in chans[i]):
                    chans[i].append(e)
                    break
        return chans

    def do_GET(self):
        if "/stream/" in self.path:
            try:
                idx = int(self.path.split('/')[-1])
                chans = self.get_organized_events()
                now = datetime.utcnow()
                sid = "184813" # Fallback RDS
                for m in chans.get(idx, []):
                    if m['start'] <= now <= m['stop']:
                        sid = CH_DATABASE.get(m['ch_key'], {}).get("id", "184813")
                        break
                self.send_response(302); self.send_header('Location', f"{STREAM_BASE}/{sid}"); self.end_headers()
            except:
                self.send_response(302); self.send_header('Location', f"{STREAM_BASE}/184813"); self.end_headers()
        elif self.path.endswith('.m3u'):
            host = self.headers.get('Host')
            self.send_response(200); self.send_header('Content-type', 'text/plain'); self.end_headers()
            m3u = "#EXTM3U\n" + "\n".join([f'#EXTINF:-1 tvg-id="CHOIX.{i}",CHOIX {i}\nhttp://{host}/api/stream/{i}' for i in range(1,6)])
            self.wfile.write(m3u.encode('utf-8'))
        else:
            self.generate_xml_output()

    def generate_xml_output(self):
        chans = self.get_organized_events()
        now = datetime.utcnow()
        self.send_response(200); self.send_header('Content-type', 'application/xml; charset=utf-8'); self.end_headers()
        xml = '<?xml version="1.0" encoding="UTF-8"?><tv>'
        for i in range(1, 6):
            xml += f'<channel id="CHOIX.{i}"><display-name>CHOIX {i}</display-name></channel>'
            cursor = (now - timedelta(hours=6))
            for p in sorted(chans[i], key=lambda x: x['start']):
                st, en = p['start'].strftime("%Y%m%d%H%M%S"), p['stop'].strftime("%Y%m%d%H%M%S")
                info = CH_DATABASE.get(p['ch_key'], {})
                ch_name = info.get('name', p['ch_key'] if p['ch_key'] else "À CONFIRMER")
                lang = info.get('lang', "??")
                
                title = f"{p['title']} ({lang}) | {ch_name}"
                if p['start'] > cursor:
                    xml += f'<programme start="{cursor.strftime("%Y%m%d%H%M%S")} +0000" stop="{st} +0000" channel="CHOIX.{i}"><title>➡️ Suivant: {title}</title></programme>'
                xml += f'<programme start="{st} +0000" stop="{en} +0000" channel="CHOIX.{i}"><title>{title}</title><desc>Diffusé sur {ch_name} ({lang})</desc></programme>'
                cursor = p['stop']
        self.wfile.write((xml + '</tv>').encode('utf-8'))
        
