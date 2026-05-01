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

# ==========================================
#              BASE DE DONNÉES
# ==========================================
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

# Global cache container
CACHE = {"bible": [], "bible_ts": None, "org": {}, "org_ts": None}

# ==========================================
#                UTILITAIRES
# ==========================================

def get_bible():
    now = datetime.utcnow()
    if not CACHE["bible"] or not CACHE["bible_ts"] or (now - CACHE["bible_ts"]).total_seconds() > 1800:
        try:
            r = requests.get(BIBLE_URL, timeout=10)
            CACHE["bible"] = r.json()
            CACHE["bible_ts"] = now
        except: pass
    return CACHE["bible"]

def clean_name(t):
    if not t: return ""
    t = str(t).upper()
    t = re.sub(r'HOCKEY|LNH|NBA|SOCCER|FOOTBALL|CONTRE', ' ', t)
    t = re.sub(r'[ÉÈÊË]', 'E', t); t = re.sub(r'[ÀÂÄ]', 'A', t)
    t = re.sub(r'[^\w\s]', ' ', t)
    t = re.sub(r'\b(\w+)( \1\b)+', r'\1', t, flags=re.IGNORECASE)
    return t.strip()

def quick_ratio(s1, s2):
    return SequenceMatcher(None, s1, s2).ratio()
    
def parse_event_time(ev_date_str):
    return datetime.fromisoformat(ev_date_str.replace('Z', '+00:00')).astimezone(timezone.utc).replace(tzinfo=None)

def prepare_team_keywords(ev_name):
    clean_for_match = re.sub(r'\b(VS|AT)\b', '', clean_name(ev_name))
    return [w for w in clean_for_match.split() if len(w) > 3]

def parse_program_start(prog_start_str):
    raw_start = re.sub(r'\D', '', prog_start_str)[:12]
    p_start = datetime.strptime(raw_start, "%Y%m%d%H%M")
    tz_match = re.search(r'([+-]\d{4})$', prog_start_str.strip())
    if tz_match:
        offset = tz_match.group(1)
        sign = 1 if offset[0] == '+' else -1
        p_start = p_start - sign * timedelta(hours=int(offset[1:3]), minutes=int(offset[3:5]))
    return p_start

def build_search_text(prog):
    return f"{clean_name(prog.get('title', ''))} {clean_name(prog.get('sub-title', ''))} {clean_name(prog.get('desc', ''))} {clean_name(prog.get('category', ''))}"

def find_all_matches_in_bible(ev_name, bible_data, ev_date_str):
    found_hits = []
    try:
        ev_time = parse_event_time(ev_date_str)
        # On nettoie le nom de l'événement ESPN
        clean_ev = clean_name(ev_name) 
        current_teams = prepare_team_keywords(ev_name)
        
        for prog in bible_data:
            p_start = parse_program_start(prog['start'])
            # Fenêtre de 2h autour du match
            if abs((ev_time - p_start).total_seconds()) <= 7200:
                full_text = build_search_text(prog)
                
                score_match = 0
                match_count = 0
                
                for team in current_teams:
                    # Règle 1 : Match exact (ex: "CANADIENS" dans le texte)
                    if team in full_text:
                        score_match += 0.85
                        match_count += 1
                    # Règle 2 : Match partiel/flou (le ratio que tu avais)
                    else:
                        max_ratio = 0
                        for word in full_text.split():
                            if len(word) < 3: continue
                            r = quick_ratio(team, word)
                            if r > max_ratio: max_ratio = r
                        if max_ratio > 0.70: # Un peu plus strict
                            score_match += max_ratio
                            match_count += 1

                # On ne garde que si au moins une équipe (ou mot clé fort) matche
                if match_count >= 1:
                    # On normalise le score final de confiance
                    avg_confidence = score_match / len(current_teams) if current_teams else 0
                    
                    # Bonus si DEUX équipes sont trouvées (Match parfait)
                    if match_count >= 2: avg_confidence += 0.2
                    
                    found_hits.append({
                        "ch": prog['ch'], 
                        "confidence": min(avg_confidence, 1.0), 
                        "prog_ref": prog
                    })
    except Exception as e:
        pass
    return found_hits
    
def fetch_espn(url):
    try: return requests.get(url, timeout=5).json()
    except: return {}

# ==========================================
#                SERVEUR HTTP
# ==========================================
class handler(BaseHTTPRequestHandler):
    def get_organized_events(self):
        now = datetime.utcnow()
        if CACHE["org"] and CACHE["org_ts"] and (now - CACHE["org_ts"]).total_seconds() < 300:
            return CACHE["org"]

        bible = get_bible()
        events, seen = [], set()
        leagues = [("hockey","nhl"), ("basketball","nba"), ("baseball","mlb"), ("soccer","eng.1"), ("soccer","fra.1"), ("soccer","ita.1"), ("soccer","esp.1"), ("soccer","usa.1"), ("soccer","uefa.champions"), ("soccer","concacaf.nations")]

        urls = []
        for day in range(2):
            ds = (now + timedelta(days=day)).strftime("%Y%m%d")
            for sp, lg in leagues:
                urls.append((f"https://site.api.espn.com/apis/site/v2/sports/{sp}/{lg}/scoreboard?dates={ds}", lg, day))

        with ThreadPoolExecutor(max_workers=10) as exe:
            futures = {exe.submit(fetch_espn, u): (lg, is_tomorrow) for u, lg, is_tomorrow in urls}
            for f in futures:
                lg, is_tomorrow = futures[f]
                data = f.result()
                if not data: continue
                
                for ev in data.get('events', []):
                    display_title = str(ev['name']).upper()
                    if display_title in seen: continue
                    
                    hits = find_all_matches_in_bible(display_title, bible, ev['date'])
                    
                    if not hits:
                        if is_tomorrow:
                            best_ch_key, final_score = "A_CONFIRMER", 0
                        else: continue
                    else:
                        potential_channel_hits = []
                        for hit in hits:
                            ch_key = hit['ch']
                            temp_score = PRIORITY_CONFIG["LEAGUES"].get(lg, 100) + (hit['confidence'] * 400)
                            full_text_epg = build_search_text(hit['prog_ref'])
                            sport_keywords = {"nhl": ["HOCKEY", "LNH"], "mlb": ["BASEBALL", "MLB"], "nba": ["BASKETBALL", "NBA"], "soccer": ["SOCCER", "FOOT", "UEFA"]}
                            if any(k in full_text_epg for k in sport_keywords.get(lg, [])): temp_score += 300 
                            else: temp_score -= 400
                            for tk, bonus in PRIORITY_CONFIG["TEAMS"].items():
                                if tk in display_title: temp_score += bonus
                            if lg == "nhl" and ch_key in CANADA_HOCKEY_IDS: temp_score += PRIORITY_CONFIG["CHANNELS"]["BONUS_HOCKEY_CANADA"]
                            info = CH_DATABASE.get(ch_key, {})
                            if info.get("lang") == "FR" and any(x in lg for x in ["soccer", "eng.1", "fra.1"]): temp_score += PRIORITY_CONFIG["CHANNELS"]["BONUS_FRENCH"]
                            if ch_key in CANADA_HOCKEY_IDS or "Sky" in info.get("name", ""): temp_score += PRIORITY_CONFIG["CHANNELS"]["BONUS_ENGLISH_PREMIUM"]
                            if ch_key and ("TVA" in str(ch_key).upper() or "184811" in str(ch_key)): temp_score += PRIORITY_CONFIG["CHANNELS"]["PENALTY_TVA"]
                            potential_channel_hits.append({"ch_key": ch_key, "score": temp_score})

                        potential_channel_hits.sort(key=lambda x: x['score'], reverse=True)
                        best_ch_key, final_score = potential_channel_hits[0]['ch_key'], potential_channel_hits[0]['score']

                    events.append({
                        "title": display_title, "score": final_score, "league": lg,
                        "start": datetime.strptime(ev['date'], "%Y-%m-%dT%H:%MZ"), 
                        "stop": datetime.strptime(ev['date'], "%Y-%m-%dT%H:%MZ") + timedelta(hours=3), 
                        "ch_key": best_ch_key
                    })
                    seen.add(display_title)

        events.sort(key=lambda x: x['score'], reverse=True)
        chans = {i: [] for i in range(1, 6)}
        for e in events:
            buffered_start = e['start'] - timedelta(minutes=30)
            for i in range(1, 6):
                can_fit, final_start = True, buffered_start
                for ex in chans[i]:
                    if not (e['stop'] <= ex['display_start'] or buffered_start >= ex['stop']):
                        if ex['stop'] <= e['start']: final_start = ex['stop']
                        else: can_fit = False; break
                if can_fit:
                    e['display_start'] = final_start
                    chans[i].append(e); break
        
        CACHE["org"], CACHE["org_ts"] = chans, now
        return chans

    def do_GET(self):
        if "/stream/" in self.path:
            try:
                idx = int(self.path.split('/')[-1])
                chans = self.get_organized_events()
                now, sid = datetime.utcnow(), "184813"
                for m in chans.get(idx, []):
                    if m['display_start'] <= now <= m['stop']:
                        sid = CH_DATABASE.get(m['ch_key'], {}).get("id", "184813"); break
                self.send_response(302); self.send_header('Location', f"{STREAM_BASE}/{sid}"); self.end_headers()
            except: self.send_response(302); self.send_header('Location', f"{STREAM_BASE}/184813"); self.end_headers()
        elif self.path.endswith('.m3u'):
            self.send_response(200); self.send_header('Content-type', 'text/plain'); self.end_headers()
            m3u = "#EXTM3U\n"
            for i in range(1,6): m3u += f'#EXTINF:-1 tvg-id=\"CHOIX.{i}\",CHOIX {i}\nhttp://{self.headers.get("Host")}/stream/{i}\n'
            self.wfile.write(m3u.encode('utf-8'))
        else: self.generate_xml_output()

    def generate_xml_output(self):
        chans = self.get_organized_events()
        now = datetime.utcnow()
        xml_out = '<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<tv>'
        for i in range(1, 6):
            xml_out += f'\n<channel id=\"CHOIX.{i}\"><display-name>CHOIX {i}</display-name></channel>'
            cursor = now - timedelta(hours=12)
            for p in sorted(chans[i], key=lambda x: x['display_start']):
                disp_st, live_st, live_en = p['display_start'].strftime("%Y%m%d%H%M%S") + " +0000", p['start'].strftime("%Y%m%d%H%M%S") + " +0000", p['stop'].strftime("%Y%m%d%H%M%S") + " +0000"
                
                ch_name = "À CONFIRMER" if p['ch_key'] == "A_CONFIRMER" else CH_DATABASE.get(p['ch_key'], {}).get('name', "SOURCE")
                icon = SPORT_ICONS.get(p['league'], SPORT_ICONS['default'])
                
                # ESCAPE XML VITAL
                title_clean = html.escape(f'{p["title"]} | {ch_name}')
                ch_name_clean = html.escape(ch_name)

                if p['display_start'] > cursor: xml_out += f'\n<programme start=\"{cursor.strftime("%Y%m%d%H%M%S")} +0000\" stop=\"{disp_st}\" channel=\"CHOIX.{i}\"><title>À venir: {title_clean}</title></programme>'
                if p['display_start'] < p['start']: xml_out += f'\n<programme start=\"{disp_st}\" stop=\"{live_st}\" channel=\"CHOIX.{i}\"><title>⏳ PRE-MATCH: {icon} {title_clean}</title><desc>Source: {ch_name_clean}</desc></programme>'
                xml_out += f'\n<programme start=\"{live_st}\" stop=\"{live_en}\" channel=\"CHOIX.{i}\"><title>🔴 LIVE: {icon} {title_clean}</title><desc>Diffuseur: {ch_name_clean} | Score: {round(p["score"])}</desc></programme>'
                cursor = p['stop']
        xml_out += '\n</tv>'
        self.send_response(200); self.send_header('Content-Type', 'application/xml; charset=utf-8'); self.end_headers()
        self.wfile.write(xml_out.encode('utf-8'))

if __name__ == "__main__":
    server = HTTPServer(('0.0.0.0', 5000), handler)
    server.serve_forever()
