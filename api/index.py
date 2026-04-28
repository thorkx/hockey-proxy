from flask import Flask, Response, request, redirect, make_response
import requests
from datetime import datetime, timedelta
import pytz

app = Flask(__name__)

# =================================================================
# 1. CONFIGURATION & MAPPING
# =================================================================
USER, PASS, BASE_DOMAIN = "tDcJnv4jMM", "2khBtbUZuV", "omegatv.live:80"

# Remplace par ton URL GitHub réelle pour le fichier JSON
JSON_URL = "https://raw.githubusercontent.com/ton-username/ton-repo/main/filtered_epg.json"

P_ULTRA, P_HIGH, P_STD = 2500, 1200, 50
ULTRA_TEAMS = ["MTL", "CANADIENS", "PSG", "MCI", "F1", "BOLOGNA", "WREXHAM", "CF MONTRÉAL"]

# Mapping entre les IDs du JSON (EPG) et tes liens IPTV
CH_LINKS = {
    "RDS.ca": "184813", "RDS2.ca": "184814", "TSN1.ca": "71234", 
    "TSN2.ca": "71235", "SN_East.ca": "71518", "SN_One.ca": "71519",
    "TVASports.ca": "184811", "CanalPlus.fr": "49943", "BeINSports1.fr": "157279",
    "DAZN1.fr": "176642", "SkySportsPL.uk": "71300" 
}

def get_url(cid): return f"http://{BASE_DOMAIN}/{USER}/{PASS}/{cid}.ts"
MAPPING_DEFAULT = get_url(CH_LINKS["RDS.ca"])

# =================================================================
# 2. LE CERVEAU : RECHERCHE & CLASSEMENT
# =================================================================

def get_ranked_games():
    now = datetime.now(pytz.utc)
    all_games = []
    
    # Étape A: Charger ton petit JSON filtré (NBA, MLB, Foot Europe)
    epg_data = []
    try:
        r = requests.get(JSON_URL, timeout=5)
        if r.status_code == 200: epg_data = r.json()
    except: pass

    # Étape B: Scanner ESPN pour les horaires officiels
    leagues = [
        ('soccer/uefa.champions', 'UCL'), ('hockey/nhl', 'NHL'),
        ('basketball/nba', 'NBA'), ('baseball/mlb', 'MLB'),
        ('racing/f1', 'F1'), ('soccer/eng.1', 'EPL'), ('soccer/fra.1', 'L1')
    ]

    for path, sport_key in leagues:
        try:
            res = requests.get(f"https://site.api.espn.com/apis/site/v2/sports/{path}/scoreboard", timeout=5).json()
            for e in res.get('events', []):
                title = e['name'].replace(" at ", " @ ")
                start_dt = datetime.strptime(e['date'].replace('Z', ''), "%Y-%m-%dT%H:%M").replace(tzinfo=pytz.utc)
                
                # --- LOGIQUE DE VALIDATION VIA JSON ---
                found_ch_id = None
                day_str = start_dt.strftime("%Y%m%d")
                
                # On cherche si une de nos chaînes diffuse ce match dans le JSON
                for entry in epg_data:
                    if entry['start'].startswith(day_str):
                        # On simplifie le match (ex: "Lakers" au lieu de "Los Angeles Lakers")
                        if any(word.lower() in entry['title'].lower() for word in title.split()):
                            found_ch_id = entry['ch']
                            break
                
                # --- CALCUL DU SCORE ---
                score = P_STD
                if any(x in title.upper() for x in ULTRA_TEAMS): score = P_ULTRA
                elif sport_key in ['UCL', 'F1']: score = P_HIGH

                # --- DÉTERMINATION DE L'URL ---
                # 1. Si trouvé dans le JSON -> On prend le lien IPTV correspondant
                # 2. Si UCL -> DAZN1 par défaut
                # 3. Sinon -> RDS par défaut
                final_link = get_url(CH_LINKS.get(found_ch_id, CH_LINKS["RDS.ca"]))
                if sport_key == 'UCL' and not found_ch_id: final_link = get_url(CH_LINKS["DAZN1.fr"])

                all_games.append({
                    'sport': sport_key, 'title': title, 'score': score, 'id': e['id'],
                    'start_dt': start_dt, 'url': final_link, 'ch_name': found_ch_id or "RDS/Default"
                })
        except: continue

    return sorted(all_games, key=lambda x: (-x['score'], x['start_dt']))

def assign_grid():
    ranked = get_ranked_games()
    grid = {i: [] for i in range(1, 6)}
    slots = {i: [] for i in range(1, 6)}
    assigned = set()
    for g in ranked:
        if g['id'] in assigned: continue
        s, e = g['start_dt'] - timedelta(minutes=45), g['start_dt'] + timedelta(hours=4)
        for i in range(1, 6):
            if not any(not (e <= os or s >= oe) for os, oe in slots[i]):
                slots[i].append((s, e))
                grid[i].append(g)
                assigned.add(g['id'])
                break
    return grid

# =================================================================
# 3. ROUTES FLASK
# =================================================================

@app.route('/')
def home(): return "Multi-Sport Smart API Active"

@app.route('/nhl-live/<ch>')
def live(ch):
    try:
        now = datetime.now(pytz.utc)
        matches = assign_grid().get(int(ch), [])
        m = next((m for m in matches if (m['start_dt'] - timedelta(minutes=45)) <= now <= (m['start_dt'] + timedelta(hours=4))), None)
        return redirect(m['url'] if m else MAPPING_DEFAULT, code=302)
    except: return redirect(MAPPING_DEFAULT)

@app.route('/playlist.m3u')
def playlist():
    h = request.host_url.rstrip('/')
    m3u = ["#EXTM3U"]
    for i in range(1, 6):
        m3u.append(f'#EXTINF:-1 tvg-id="MULTI{i}", MULTI {i}\n{h}/nhl-live/{i}')
    return Response("\n".join(m3u), mimetype='text/plain')

@app.route('/epg.xml')
def epg():
    grid = assign_grid()
    xml = ['<?xml version="1.0" encoding="UTF-8"?><tv>']
    for i in range(1, 6):
        cid = f"MULTI{i}"
        xml.append(f'<channel id="{cid}"><display-name>MULTI {i}</display-name></channel>')
        for m in sorted(grid[i], key=lambda x: x['start_dt']):
            s = m['start_dt']
            xml.append(f'<programme start="{s.strftime("%Y%m%d%H%M%S")} +0000" stop="{(s+timedelta(hours=3, minutes=30)).strftime("%Y%m%d%H%M%S")} +0000" channel="{cid}"><title lang="fr">{m["title"]} ({m["ch_name"]})</title></programme>')
    xml.append('</tv>')
    return Response("\n".join(xml), mimetype='application/xml')

if __name__ == '__main__':
    app.run()
        
