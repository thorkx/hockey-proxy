from http.server import BaseHTTPRequestHandler, HTTPServer
import requests
import json
import re
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor

# ==========================================
#        CONFIGURATION & DATABASE (REMISE À NEUF)
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

CH_DATABASE = {
    "Réseau.des.Sports.(RDS).HD.ca2": {"name": "RDS", "id": "184813"},
    "RDS2.HD.ca2": {"name": "RDS 2", "id": "184814"},
    "Réseau.des.Sports.Info.HD.ca2": {"name": "RDS Info", "id": "184815"},
    "TVA.Sports.HD.ca2": {"name": "TVA Sports", "id": "184811"},
    "TVA.Sports.2.HD.ca2": {"name": "TVA Sports 2", "id": "184812"},
    "Sportsnet.4K.ca2": {"name": "SN 4K", "id": "157674"},
    "Sportsnet.One.HD.ca2": {"name": "SN One", "id": "157675"},
    "Sportsnet.360.HD.ca2": {"name": "SN 360", "id": "71517"},
    "Sportsnet.East.HD.ca2": {"name": "SN East", "id": "71518"},
    "Sportsnet.West.HD.ca2": {"name": "SN West", "id": "71521"},
    "TSN.4K.ca2": {"name": "TSN 1", "id": "71234"},
    "One.Soccer.ca2": {"name": "OneSoccer", "id": "19320"},
    "CanalPlus.fr": {"name": "Canal+", "id": "49943"},
    "beINSPORTS1.fr": {"name": "BeIn Sports 1", "id": "49895"},
    "SkySp.PL.HD.uk": {"name": "Sky PL", "id": "74322"},
    "SkySp.F1.HD.uk": {"name": "Sky F1", "id": "74316"},
    "ESPN.HD.us2": {"name": "ESPN", "id": "18345"},
    "Fox.Sports.1.HD.us2": {"name": "FS1", "id": "18242"}
}

# Cache global via dictionnaire pour stabilité Vercel
GLOBAL_DATA = {
    "bible": [],
    "bible_ts": None,
    "organized": {},
    "organized_ts": None
}

# ==========================================
#                LOGIQUE CORE
# ==========================================

def get_bible():
    global GLOBAL_DATA
    now = datetime.utcnow()
    if not GLOBAL_DATA["bible"] or not GLOBAL_DATA["bible_ts"] or (now - GLOBAL_DATA["bible_ts"]).total_seconds() > 1800:
        try:
            r = requests.get("https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json", timeout=10)
            GLOBAL_DATA["bible"] = r.json()
            GLOBAL_DATA["bible_ts"] = now
        except: pass
    return GLOBAL_DATA["bible"]

def find_best_match(ev_name, bible, ev_date_str):
    best_hit = None
    max_quality = -999
    try:
        ev_time = datetime.fromisoformat(ev_date_str.replace('Z', '+00:00')).replace(tzinfo=None)
        teams = [w for w in re.sub(r'[^\w\s]', '', ev_name.upper()).split() if len(w) > 3 and w not in ["HOCKEY", "SOCCER"]]
        
        for prog in bible:
            p_start = datetime.strptime(re.sub(r'\D', '', prog['start'])[:12], "%Y%m%d%H%M")
            if abs((ev_time - p_start).total_seconds()) > 7200: continue
            
            p_stop = datetime.strptime(re.sub(r'\D', '', prog['stop'])[:12], "%Y%m%d%H%M")
            duration = (p_stop - p_start).total_seconds() / 60
            
            quality = 50 if 110 <= duration <= 240 else (-100 if duration < 45 else 0)
            text = f"{prog.get('title','')} {prog.get('desc','')}".upper()
            
            matches = sum(1 for t in teams if t[:4] in text)
            if matches == 0: continue
            
            quality += (matches * 40)
            if any(kw in text for kw in ['LIVE', 'DIRECT', 'MATCH']): quality += 40
            if any(kw in text for kw in ['RECAP', 'HIGHLIGHT', '30 IN 30']): quality -= 150

            if quality > max_quality:
                max_quality = quality
                best_hit = {"ch": prog['ch'], "quality": quality}
    except: pass
    return best_hit if max_quality > 40 else None

# ==========================================
#                HANDLER VERCEL
# ==========================================

class handler(BaseHTTPRequestHandler):
    def get_organized_events(self):
        global GLOBAL_DATA
        now = datetime.utcnow()
        if GLOBAL_DATA["organized_ts"] and (now - GLOBAL_DATA["organized_ts"]).total_seconds() < 300:
            return GLOBAL_DATA["organized"]

        bible = get_bible()
        events, seen = [], set()
        # Remise de toutes tes ligues
        leagues = [
            ("hockey","nhl"), ("basketball","nba"), ("baseball","mlb"), 
            ("soccer","eng.1"), ("soccer","fra.1"), ("soccer","ita.1"), 
            ("soccer","esp.1"), ("soccer","uefa.champions"), ("soccer","usa.1")
        ]

        for d in range(2):
            ds = (now + timedelta(days=d)).strftime("%Y%m%d")
            for sp, lg in leagues:
                try:
                    r = requests.get(f"https://site.api.espn.com/apis/site/v2/sports/{sp}/{lg}/scoreboard?dates={ds}", timeout=5)
                    data = r.json()
                    for ev in data.get('events', []):
                        name = ev['name'].upper()
                        if name in seen: continue
                        
                        best = find_best_match(name, bible, ev['date'])
                        if not best:
                            if d >= 1: best_ch, score = "A_CONFIRMER", 10
                            else: continue
                        else:
                            best_ch, score = best['ch'], PRIORITY_CONFIG["LEAGUES"].get(lg, 100) + best['quality']
                            for tk, b in PRIORITY_CONFIG["TEAMS"].items():
                                if tk in name: score += b

                        events.append({
                            "title": name, "score": score, "ch_key": best_ch,
                            "start": datetime.strptime(ev['date'], "%Y-%m-%dT%H:%MZ"),
                            "stop": datetime.strptime(ev['date'], "%Y-%m-%dT%H:%MZ") + timedelta(hours=3)
                        })
                        seen.add(name)
                except: continue

        events.sort(key=lambda x: x['score'], reverse=True)
        chans = {i: [] for i in range(1, 6)}
        for e in events:
            for i in range(1, 6):
                can_fit = True
                e_start = e['start'] - timedelta(minutes=30)
                for ex in chans[i]:
                    if not (e['stop'] <= ex['start_display'] or e_start >= ex['stop']):
                        can_fit = False; break
                if can_fit:
                    e['start_display'] = e_start
                    chans[i].append(e); break

        GLOBAL_DATA["organized"] = chans
        GLOBAL_DATA["organized_ts"] = now
        return chans

    def do_GET(self):
        try:
            chans = self.get_organized_events()
            if "/stream/" in self.path:
                try:
                    idx = int(self.path.split('/')[-1])
                    now = datetime.utcnow()
                    sid = "184813"
                    for m in chans.get(idx, []):
                        if m['start_display'] <= now <= m['stop']:
                            sid = CH_DATABASE.get(m['ch_key'], {"id": "184813"}).get("id", "184813")
                            break
                    self.send_response(302)
                    self.send_header('Location', f"http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV/{sid}")
                    self.end_headers()
                except:
                    self.send_response(302)
                    self.send_header('Location', "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV/184813")
                    self.end_headers()
            elif self.path.endswith('.m3u'):
                self.send_response(200); self.send_header('Content-type', 'text/plain'); self.end_headers()
                res = "#EXTM3U\n"
                for i in range(1,6):
                    res += f'#EXTINF:-1 tvg-id="CHOIX.{i}",CHOIX {i}\nhttp://{self.headers.get("Host")}/stream/{i}\n'
                self.wfile.write(res.encode('utf-8'))
            else:
                self.send_response(200); self.send_header('Content-Type', 'application/xml'); self.end_headers()
                xml = '<?xml version="1.0" encoding="UTF-8"?><tv>'
                for i in range(1, 6):
                    xml += f'<channel id="CHOIX.{i}"><display-name>CHOIX {i}</display-name></channel>'
                    for p in chans[i]:
                        st = p['start_display'].strftime("%Y%m%d%H%M%S") + " +0000"
                        en = p['stop'].strftime("%Y%m%d%H%M%S") + " +0000"
                        ch_n = CH_DATABASE.get(p['ch_key'], {"name": "A CONFIRMER"})["name"]
                        xml += f'<programme start="{st}" stop="{en}" channel="CHOIX.{i}"><title>{p["title"]} | {ch_n}</title></programme>'
                self.wfile.write((xml + '</tv>').encode('utf-8'))
        except Exception as e:
            self.send_response(200); self.send_header('Content-Type', 'text/plain'); self.end_headers()
            self.wfile.write(f"Erreur: {str(e)}".encode())

if __name__ == "__main__":
    server = HTTPServer(('0.0.0.0', 5000), handler)
    server.serve_forever()
    
