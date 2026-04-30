from http.server import BaseHTTPRequestHandler, HTTPServer
import requests
import json
import re
import html
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor

# ==========================================
#        CONFIGURATION DES PRIORITÉS
# ==========================================
PRIORITY_CONFIG = {
    "LEAGUES": {
        "nhl": 800, "nba": 250, "uefa.champions": 375,
        "eng.1": 350, "fra.1": 350, "ita.1": 350, "esp.1": 350,
        "uefa.europa": 350, "mlb": 200, "usa.1": 450,
        "concacaf.nations": 600, "concacaf.champions": 500
    },
    "TEAMS": {
        "CANADIENS": 3500, "RAPTORS": 1000, "BLUE JAYS": 1000, 
        "CF MONTREAL": 1000, "WREXHAM": 1200,
        "SUPRA": 1500, "CanMNT": 2000, "CanWNT" : 2000 
    },
    "CHANNELS": {
        "BONUS_HOCKEY_CANADA": 1200, 
        "BONUS_ENGLISH_PREMIUM": 500, 
        "BONUS_FRENCH": 300, 
        "PENALTY_TVA": -150 
    }
}

CANADA_HOCKEY_IDS = [
    "Réseau.des.Sports.(RDS).HD.ca2", "RDS2.HD.ca2", "Réseau.des.Sports.Info.HD.ca2"
    "TVA.Sports.HD.ca2", "TVA.Sports.2.HD.ca2",
    "TSN.4K.ca2", "TSN2", "TSN3", "TSN4", "TSN5",
    "Sportsnet.4K.ca2", "Sportsnet.One.HD.ca2", "Sportsnet.360.HD.ca2", 
    "Sportsnet.East.HD.ca2", "Sportsnet.West.HD.ca2", "One.Soccer.ca2", "Sportsnet.World.HD.ca2"
]

# ==========================================
#              BASE DE DONNÉES
# ==========================================
# Assure-toi que cette URL pointe bien vers ton fichier généré par le nouveau bot
BIBLE_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

CH_DATABASE = {
    "Réseau.des.Sports.(RDS).HD.ca2": {"name": "RDS", "id": "184813", "lang": "FR"},
    "RDS2.HD.ca2": {"name": "RDS 2", "id": "184814", "lang": "FR"},
    "Réseau.des.Sports.Info.HD.ca2": {"name": "RDS Info", "id": "184815", "lang": "FR"},
    "TVA.Sports.HD.ca2": {"name": "TVA Sports", "id": "184811", "lang": "FR"},
    "TVA.Sports.2.HD.ca2": {"name": "TVA Sports 2", "id": "184812", "lang": "EN"},
    "Sportsnet.4K.ca2": {"name": "Sportsnet 4K", "id": "157674", "lang": "EN"},
    "Sportsnet.One.HD.ca2": {"name": "SN One", "id": "157675", "lang": "EN"},
    "Sportsnet.360.HD.ca2": {"name": "SN 360", "id": "71517", "lang": "EN"},
    "Sportsnet.East.HD.ca2": {"name": "SN East", "id": "71518", "lang": "EN"},
    "Sportsnet.West.HD.ca2": {"name": "SN West", "id": "71521", "lang": "EN"},
    "Sportsnet.(Pacific).HD.ca2": {"name": "SN Pacific", "id": "71520", "lang": "EN"},
    "TSN.4K.ca2": {"name": "TSN 1", "id": "71234", "lang": "EN"},
    "TSN.2.ca2": {"name": "TSN 2", "id": "71235", "lang": "EN"},
    "TSN.3.ca2": {"name": "TSN 3", "id": "71236", "lang": "EN"},
    "TSN.4.ca2": {"name": "TSN 4", "id": "71237", "lang": "EN"},
    "TSN.5.ca2": {"name": "TSN 5", "id": "71238", "lang": "EN"},
    "One.Soccer.ca2": {"name": "OneSoccer", "id": "19320", "lang": "EN"},
    "Sportsnet.World.HD.ca2": {"name": "SN World", "id": "71526", "lang": "EN"},
    "CanalPlus.fr": {"name": "Canal+", "id": "49943", "lang": "FR"},
    "CanalPlusSport.fr": {"name": "Canal+ Sport", "id": "49951", "lang": "FR"},
    "CanalPlusSport360.fr": {"name": "Canal+ Sport 360", "id": "83038", "lang": "FR"},
    "beINSPORTS1.fr": {"name": "BeIn Sports 1", "id": "49895", "lang": "FR"},
    "beINSPORTS2.fr": {"name": "BeIn Sports 2", "id": "49896", "lang": "FR"},
    "beINSPORTS3.fr": {"name": "BeIn Sports 3", "id": "49897", "lang": "FR"},
    "beINSPORTSMAX4.fr": {"name": "BeIn Max 4", "id": "49903", "lang": "FR"},
    "beINSPORTSMAX5.fr": {"name": "BeIn Max 5", "id": "83080", "lang": "FR"},
    "beINSPORTSMAX6.fr": {"name": "BeIn Max 6", "id": "83081", "lang": "FR"},
    "beINSPORTSMAX7.fr": {"name": "BeIn Max 7", "id": "83082", "lang": "FR"},
    "beINSPORTSMAX8.fr": {"name": "BeIn Max 8", "id": "49904", "lang": "FR"},
    "beINSPORTSMAX9.fr": {"name": "BeIn Max 9", "id": "49905", "lang": "FR"},
    "beINSPORTSMAX10.fr": {"name": "BeIn Max 10", "id": "49906", "lang": "FR"},
    "Eurosport1.fr": {"name": "Eurosport 1", "id": "50009", "lang": "FR"},
    "Eurosport2.fr": {"name": "Eurosport 2", "id": "50010", "lang": "FR"},
    "RMCSport1.fr": {"name": "RMC Sport 1", "id": "50145", "lang": "FR"},
    "RMCSport2.fr": {"name": "RMC Sport 2", "id": "50147", "lang": "FR"},
    "TNT.Sports.1.HD.uk": {"name": "TNT Sports 1", "id": "74357", "lang": "EN"},
    "TNT.Sports.2.HD.uk": {"name": "TNT Sports 2", "id": "74360", "lang": "EN"},
    "TNT.Sports.3.HD.uk": {"name": "TNT Sports 3", "id": "74363", "lang": "EN"},
    "SkySp.PL.HD.uk": {"name": "Sky PL", "id": "74322", "lang": "EN"},
    "SkySp.F1.HD.uk": {"name": "Sky F1", "id": "74316", "lang": "EN"},
    "ESPN.HD.us2": {"name": "ESPN", "id": "18345", "lang": "EN"},
    "ESPN2.HD.us2": {"name": "ESPN 2", "id": "18346", "lang": "EN"},
    "ESPN.Deportes.HD.us2": {"name": "ESPN Deportes", "id": "18356", "lang": "ES"},
    "Fox.Sports.1.HD.us2": {"name": "FS1", "id": "18242", "lang": "EN"},
    "CBS.Sports.Network.HD.us2": {"name": "CBS Sports", "id": "18335", "lang": "EN"},
    "beIN.Sports.USA.HD.us2": {"name": "BeIn USA", "id": "18312", "lang": "EN"}
}

SPORT_ICONS = {"nhl": "🏒", "nba": "🏀", "mlb": "⚾", "soccer": "⚽", "uefa.champions": "🇪🇺", "default": "🏆"}

# ==========================================
#                UTILITAIRES
# ==========================================
def escape_xml(text):
    if not text: return ""
    return html.escape(text).encode('ascii', 'xmlcharrefreplace').decode()

def clean_name(t):
    if not t: return ""
    t = t.upper()
    t = re.sub(r'HOCKEY|LNH|NBA|SOCCER|FOOTBALL| AT | VS |CONTRE', ' ', t)
    t = re.sub(r'[ÉÈÊË]', 'E', t); t = re.sub(r'[ÀÂÄ]', 'A', t)
    return re.sub(r'[^\w\s]', ' ', t)
    
def find_all_matches_in_bible(ev_name, bible_data, ev_date_str):
    found_keys = set()
    try:
        ev_time = datetime.fromisoformat(ev_date_str.replace('Z', '+00:00')).astimezone(timezone.utc).replace(tzinfo=None)

        # On prépare les mots-clés des équipes
        current_teams = [w for w in clean_name(ev_name).split() if len(w) > 3 and w not in ["MONTREAL", "TORONTO", "UNITED", "CITY"]]
        if "CANADIENS" in ev_name.upper() and "CANADIENS" not in current_teams:
            current_teams.append("CANADIENS")

        for prog in bible_data:
            raw_start = re.sub(r'\D', '', prog['start'])[:12]
            p_start = datetime.strptime(raw_start, "%Y%m%d%H%M")

            tz_match = re.search(r'([+-]\d{4})$', prog['start'].strip())
            if tz_match:
                offset = tz_match.group(1)
                sign = 1 if offset[0] == '+' else -1
                hours = int(offset[1:3])
                minutes = int(offset[3:5])
                p_start = p_start - sign * timedelta(hours=hours, minutes=minutes)

            # --- FENÊTRE ÉLARGIE À 90 MIN (5400s) ---
            if abs((ev_time - p_start).total_seconds()) <= 5400:
                # RECHERCHE MULTI-CHAMPS (Titre + Sous-titre + Desc + Catégorie)
                full_text = (
                    clean_name(prog.get('title', '')) + " " + 
                    clean_name(prog.get('sub-title', '')) + " " + 
                    clean_name(prog.get('desc', '')) + " " + 
                    clean_name(prog.get('category', ''))
                )

                if any(team in full_text for team in current_teams):
                    found_keys.add(prog['ch'])
    except Exception:
        pass
    return list(found_keys)
    
def fetch_espn(url):
    try: return requests.get(url, timeout=5).json()
    except: return {}

# ==========================================
#                SERVEUR HTTP
# ==========================================
class handler(BaseHTTPRequestHandler):
    def get_organized_events(self):
        try: bible = requests.get(BIBLE_URL, timeout=5).json()
        except: bible = []
        now = datetime.utcnow()
        events, seen = [], set()
        
        leagues = [
            ("hockey","nhl"), ("basketball","nba"), ("baseball","mlb"),
            ("soccer","eng.1"), ("soccer","fra.1"), ("soccer","ita.1"),
            ("soccer","esp.1"), ("soccer","usa.1"), ("soccer","uefa.champions"),
            ("soccer","concacaf.nations")
        ]

        urls = []
        # On regarde aujourd'hui et demain
        for day in range(2):
            ds = (now + timedelta(days=day)).strftime("%Y%m%d")
            for sp, lg in leagues:
                urls.append((f"https://site.api.espn.com/apis/site/v2/sports/{sp}/{lg}/scoreboard?dates={ds}", lg))

        with ThreadPoolExecutor(max_workers=10) as exe:
            futures = {exe.submit(fetch_espn, u): lg for u, lg in urls}
            for f in futures:
                lg = futures[f]
                for ev in f.result().get('events', []):
                    name = ev['name'].upper()
                    if name in seen: continue
                    
                    all_possible_keys = find_all_matches_in_bible(name, bible, ev['date'])
                    if not all_possible_keys: continue

                    potential_channel_hits = []
                    for ch_key in all_possible_keys:
                        temp_score = PRIORITY_CONFIG["LEAGUES"].get(lg, 100)
                        for team, bonus in PRIORITY_CONFIG["TEAMS"].items():
                            if team in name: temp_score += bonus
                        
                        if lg == "nhl" and ch_key in CANADA_HOCKEY_IDS:
                            temp_score += PRIORITY_CONFIG["CHANNELS"]["BONUS_HOCKEY_CANADA"]
                        
                        info = CH_DATABASE.get(ch_key, {})
                        is_soccer = any(x in lg for x in ["soccer", "eng.1", "fra.1", "uefa", "usa.1", "concacaf"])
                        
                        if info.get("lang") == "FR" and is_soccer:
                            temp_score += PRIORITY_CONFIG["CHANNELS"]["BONUS_FRENCH"]
                        
                        if ch_key in CANADA_HOCKEY_IDS or "Sky" in info.get("name", ""):
                            temp_score += PRIORITY_CONFIG["CHANNELS"]["BONUS_ENGLISH_PREMIUM"]

                        if ch_key and ("TVA" in str(ch_key).upper() or "184811" in str(ch_key)):
                            temp_score += PRIORITY_CONFIG["CHANNELS"]["PENALTY_TVA"]
                        
                        potential_channel_hits.append({"ch_key": ch_key, "score": temp_score})

                    potential_channel_hits.sort(key=lambda x: x['score'], reverse=True)
                    best_hit = potential_channel_hits[0]

                    events.append({
                        "title": name, "score": best_hit['score'], "league": lg,
                        "start": datetime.strptime(ev['date'], "%Y-%m-%dT%H:%MZ"), 
                        "stop": datetime.strptime(ev['date'], "%Y-%m-%dT%H:%MZ") + timedelta(hours=3), 
                        "ch_key": best_hit['ch_key']
                    })
                    seen.add(name)

        events.sort(key=lambda x: x['score'], reverse=True)
        chans = {i: [] for i in range(1, 6)}
        
        for e in events:
            buffered_start = e['start'] - timedelta(minutes=30)
            for i in range(1, 6):
                can_fit = True
                final_start = buffered_start
                for existing in chans[i]:
                    if not (e['stop'] <= existing['display_start'] or buffered_start >= existing['stop']):
                        if existing['stop'] <= e['start']:
                            final_start = existing['stop']
                        else:
                            can_fit = False
                            break
                if can_fit:
                    e['display_start'] = final_start
                    chans[i].append(e)
                    break
        return chans

    def do_GET(self):
        if "/stream/" in self.path:
            try:
                idx = int(self.path.split('/')[-1])
                chans = self.get_organized_events()
                now = datetime.utcnow()
                sid = "184813" 
                for m in chans.get(idx, []):
                    if m['display_start'] <= now <= m['stop']:
                        sid = CH_DATABASE.get(m['ch_key'], {}).get("id", "184813")
                        break
                self.send_response(302); self.send_header('Location', f"{STREAM_BASE}/{sid}"); self.end_headers()
            except:
                self.send_response(302); self.send_header('Location', f"{STREAM_BASE}/184813"); self.end_headers()
        elif self.path.endswith('.m3u'):
            self.send_response(200); self.send_header('Content-type', 'text/plain'); self.end_headers()
            host = self.headers.get('Host')
            m3u = "#EXTM3U\n"
            for i in range(1,6):
                m3u += f'#EXTINF:-1 tvg-id="CHOIX.{i}",CHOIX {i}\nhttp://{host}/stream/{i}\n'
            self.wfile.write(m3u.encode('utf-8'))
        else:
            self.generate_xml_output()

    def generate_xml_output(self):
        chans = self.get_organized_events()
        now = datetime.utcnow()
        xml_out = '<?xml version="1.0" encoding="UTF-8"?>\n<tv>'
        for i in range(1, 6):
            xml_out += f'\n<channel id="CHOIX.{i}"><display-name>CHOIX {i}</display-name></channel>'
            cursor = now - timedelta(hours=12)
            for p in sorted(chans[i], key=lambda x: x['display_start']):
                disp_st = p['display_start'].strftime("%Y%m%d%H%M%S") + " +0000"
                live_st = p['start'].strftime("%Y%m%d%H%M%S") + " +0000"
                live_en = p['stop'].strftime("%Y%m%d%H%M%S") + " +0000"
                info = CH_DATABASE.get(p['ch_key'], {})
                ch_name = info.get('name', "SOURCE")
                icon = SPORT_ICONS.get(p['league'], SPORT_ICONS['default'])
                title = f'{p["title"]} | {ch_name}'
                if p['display_start'] > cursor:
                    xml_out += f'\n<programme start="{cursor.strftime("%Y%m%d%H%M%S")} +0000" stop="{disp_st}" channel="CHOIX.{i}"><title>À venir: {title}</title></programme>'
                if p['display_start'] < p['start']:
                    xml_out += f'\n<programme start="{disp_st}" stop="{live_st}" channel="CHOIX.{i}"><title>⏳ PRE-MATCH: {icon} {title}</title><desc>Source: {ch_name}</desc></programme>'
                xml_out += f'\n<programme start="{live_st}" stop="{live_en}" channel="CHOIX.{i}"><title>🔴 LIVE: {icon} {title}</title><desc>Diffuseur: {ch_name} | Score: {p["score"]}</desc></programme>'
                cursor = p['stop']
        xml_out += '\n</tv>'
        self.send_response(200); self.send_header('Content-Type', 'application/xml; charset=utf-8'); self.end_headers()
        self.wfile.write(xml_out.encode('utf-8'))

if __name__ == "__main__":
    server = HTTPServer(('0.0.0.0', 5000), handler)
    print("Serveur Hockey Proxy Actif (Port 5000)")
    server.serve_forever()
    
