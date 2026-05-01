from http.server import BaseHTTPRequestHandler, HTTPServer
import requests
import json
import re
import html
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher

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
    "Réseau.des.Sports.(RDS).HD.ca2", "RDS2.HD.ca2", "Réseau.des.Sports.Info.HD.ca2",
    "TVA.Sports.HD.ca2", "TVA.Sports.2.HD.ca2",
    "TSN.4K.ca2", "TSN2", "TSN3", "TSN4", "TSN5",
    "Sportsnet.4K.ca2", "Sportsnet.One.HD.ca2", "Sportsnet.360.HD.ca2", 
    "Sportsnet.East.HD.ca2", "Sportsnet.West.HD.ca2", "One.Soccer.ca2", "Sportsnet.World.HD.ca2"
]

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
    "TSN.4K.ca2": {"name": "TSN 1", "id": "71234", "lang": "EN"},
    "One.Soccer.ca2": {"name": "OneSoccer", "id": "19320", "lang": "EN"},
    "CanalPlus.fr": {"name": "Canal+", "id": "49943", "lang": "FR"},
    "beINSPORTS1.fr": {"name": "BeIn Sports 1", "id": "49895", "lang": "FR"},
    "SkySp.PL.HD.uk": {"name": "Sky PL", "id": "74322", "lang": "EN"},
    "SkySp.F1.HD.uk": {"name": "Sky F1", "id": "74316", "lang": "EN"},
    "ESPN.HD.us2": {"name": "ESPN", "id": "18345", "lang": "EN"},
    "Fox.Sports.1.HD.us2": {"name": "FS1", "id": "18242", "lang": "EN"}
}

SPORT_ICONS = {"nhl": "🏒", "nba": "🏀", "mlb": "⚾", "soccer": "⚽", "default": "🏆"}

# ==========================================
#                UTILITAIRES
# ==========================================
BIBLE_CACHE = {"data": [], "timestamp": None}
CACHE_ORGANIZED = {"chans": {}, "timestamp": None}

def get_bible():
    now = datetime.utcnow()
    if not BIBLE_CACHE["data"] or not BIBLE_CACHE["timestamp"] or (now - BIBLE_CACHE["timestamp"]).total_seconds() > 1800:
        try:
            r = requests.get("https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json", timeout=10)
            BIBLE_CACHE["data"] = r.json()
            BIBLE_CACHE["timestamp"] = now
        except: pass
    return BIBLE_CACHE["data"]

def clean_name(t):
    if not t: return ""
    t = str(t).upper()
    t = re.sub(r'[^\w\s]', ' ', t)
    return t.strip()

def parse_event_time(ev_date_str):
    return datetime.fromisoformat(ev_date_str.replace('Z', '+00:00')).astimezone(timezone.utc).replace(tzinfo=None)

def parse_program_start(prog_start_str):
    raw = re.sub(r'\D', '', prog_start_str)[:12]
    return datetime.strptime(raw, "%Y%m%d%H%M")

def prepare_team_keywords(ev_name):
    clean = re.sub(r'\b(VS|AT)\b', '', clean_name(ev_name))
    return [w for w in clean.split() if len(w) > 3]

def build_search_text(prog):
    return f"{prog.get('title', '')} {prog.get('desc', '')} {prog.get('category', '')}".upper()

# ==========================================
#        LOGIQUE DE DÉDUCTION (QUALITÉ)
# ==========================================
def find_best_match_in_bible(ev_name, bible_data, ev_date_str, lg):
    best_hit = None
    max_quality = -999
    ev_time = parse_event_time(ev_date_str)
    teams = prepare_team_keywords(ev_name)
    
    for prog in bible_data:
        p_start = parse_program_start(prog['start'])
        if abs((ev_time - p_start).total_seconds()) > 7200: continue
        
        quality = 0
        p_stop = parse_program_start(prog['stop'])
        duration = (p_stop - p_start).total_seconds() / 60
        
        # Filtres de durée
        if 110 <= duration <= 240: quality += 50 
        elif duration < 45: quality -= 120
        
        full_text = build_search_text(prog)
        match_count = sum(1 for t in teams if t[:4] in full_text)
        if match_count == 0: continue
        
        quality += (match_count * 40)
        cat = str(prog.get('category', '')).upper()
        title = str(prog.get('title', '')).upper()
        
        if any(kw in cat or kw in title for kw in ['LIVE', 'DIRECT', 'MATCH']): quality += 40
        if any(kw in cat or kw in title for kw in ['TALK', 'NEWS', 'RECAP', 'HIGHLIGHT', '30 IN 30']): quality -= 150

        if quality > max_quality:
            max_quality = quality
            best_hit = {"ch": prog['ch'], "quality": quality}
            
    return best_hit if max_quality > 40 else None

def fetch_espn(url):
    try: return requests.get(url, timeout=5).json()
    except: return {}

# ==========================================
#                SERVEUR HTTP
# ==========================================
class handler(BaseHTTPRequestHandler):
    def get_organized_events(self):
        now = datetime.utcnow()
        if CACHE_ORGANIZED["timestamp"] and (now - CACHE_ORGANIZED["timestamp"]).total_seconds() < 300:
            return CACHE_ORGANIZED["chans"]

        bible = get_bible()
        events, seen = [], set()
        leagues = [("hockey","nhl"), ("basketball","nba"), ("baseball","mlb"), ("soccer","eng.1"), ("soccer","fra.1")]

        urls = []
        for d in range(2):
            ds = (now + timedelta(days=d)).strftime("%Y%m%d")
            for sp, lg in leagues:
                urls.append((f"https://site.api.espn.com/apis/site/v2/sports/{sp}/{lg}/scoreboard?dates={ds}", lg, d))

        with ThreadPoolExecutor(max_workers=10) as exe:
            futures = {exe.submit(fetch_espn, u): (lg, day) for u, lg, day in urls}
            for f in futures:
                lg, day_offset = futures[f]
                data = f.result()
                if not data: continue
                for ev in data.get('events', []):
                    name = str(ev['name']).upper()
                    if name in seen: continue
                    
                    best = find_best_match_in_bible(name, bible, ev['date'], lg)
                    if not best:
                        if day_offset >= 1: best_ch, f_score = "A_CONFIRMER", 10
                        else: continue
                    else:
                        best_ch, f_score = best['ch'], PRIORITY_CONFIG["LEAGUES"].get(lg, 100) + best['quality']
                        for tk, b in PRIORITY_CONFIG["TEAMS"].items():
                            if tk in name: f_score += b

                    events.append({
                        "title": name, "score": f_score, "league": lg,
                        "start": datetime.strptime(ev['date'], "%Y-%m-%dT%H:%MZ"), 
                        "stop": datetime.strptime(ev['date'], "%Y-%m-%dT%H:%MZ") + timedelta(hours=3), 
                        "ch_key": best_ch
                    })
                    seen.add(name)

        events.sort(key=lambda x: x['score'], reverse=True)
        chans = {i: [] for i in range(1, 6)}
        for e in events:
            for i in range(1, 6):
                can_fit = True
                b_st = e['start'] - timedelta(minutes=30)
                for ex in chans[i]:
                    if not (e['stop'] <= ex['display_start'] or b_st >= ex['stop']): can_fit = False; break
                if can_fit and e['ch_key'] != "A_CONFIRMER":
                    for j in range(1, 6):
                        for o in chans[j]:
                            if o['ch_key'] == e['ch_key'] and not (e['stop'] <= o['start'] or e['start'] >= o['stop']):
                                can_fit = False; break
                if can_fit:
                    e['display_start'] = b_st
                    chans[i].append(e)
                    break

        CACHE_ORGANIZED["chans"] = chans
        CACHE_ORGANIZED["timestamp"] = now
        return chans

    def do_GET(self):
        chans = self.get_organized_events()
        if "/stream/" in self.path:
            try:
                idx = int(self.path.split('/')[-1])
                now = datetime.utcnow()
                sid = "184813"
                for m in chans.get(idx, []):
                    if m['display_start'] <= now <= m['stop']:
                        sid = CH_DATABASE.get(m['ch_key'], {}).get("id", "184813"); break
                self.send_response(302); self.send_header('Location', f"http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV/{sid}"); self.end_headers()
            except: self.send_response(302); self.send_header('Location', "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV/184813"); self.end_headers()
        elif self.path.endswith('.m3u'):
            self.send_response(200); self.send_header('Content-type', 'text/plain'); self.end_headers()
            m3u = "#EXTM3U\n"
            for i in range(1,6): m3u += f'#EXTINF:-1 tvg-id="CHOIX.{i}",CHOIX {i}\nhttp://{self.headers.get("Host")}/stream/{i}\n'
            self.wfile.write(m3u.encode('utf-8'))
        else:
            xml = '<?xml version="1.0" encoding="UTF-8"?><tv>'
            for i in range(1, 6):
                xml += f'<channel id="CHOIX.{i}"><display-name>CHOIX {i}</display-name></channel>'
                cursor = datetime.utcnow() - timedelta(hours=6)
                for p in sorted(chans[i], key=lambda x: x['display_start']):
                    name = CH_DATABASE.get(p['ch_key'], {"name": "À CONFIRMER"})['name']
                    st = p['display_start'].strftime("%Y%m%d%H%M%S") + " +0000"
                    en = p['stop'].strftime("%Y%m%d%H%M%S") + " +0000"
                    xml += f'<programme start="{st}" stop="{en}" channel="CHOIX.{i}"><title>{p["title"]} | {name}</title></programme>'
            self.send_response(200); self.send_header('Content-Type', 'application/xml'); self.end_headers()
            self.wfile.write((xml + '</tv>').encode('utf-8'))

if __name__ == "__main__":
    server = HTTPServer(('0.0.0.0', 5000), handler)
    server.serve_forever()
                        
