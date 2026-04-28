from flask import Flask, Response, request, redirect, make_response
import requests
from datetime import datetime, timedelta
import pytz
import re

app = Flask(__name__)

# =================================================================
# 1. CONFIGURATION
# =================================================================
USER, PASS, BASE_DOMAIN = "tDcJnv4jMM", "2khBtbUZuV", "omegatv.live:80"

P_ULTRA, P_HIGH, P_STD = 2500, 1200, 50
ULTRA_TEAMS = ["MTL", "CAN", "CANADIENS", "MONTREAL", "CF MONTRÉAL", "TOR", "BLUE JAYS", "RAPTORS", "PSG", "MCI", "F1", "BOLOGNA", "WREXHAM"]

CH = {
    "RDS": "184813", "RDS2": "184814", "TVAS": "184811", "TVAS2": "184812",
    "SNE": "71518", "SN1": "71519", "TSN1": "71234", "OneSoccer": "18435", 
    "SkyF1": "71300", "CanalPlus": "49943", "BEIN1FR": "157279"
}
for i in range(1, 11): CH[f"DAZN{i}"] = str(176642 + (i - 1))

def get_url(cid): return f"http://{BASE_DOMAIN}/{USER}/{PASS}/{cid}.ts"

MAPPING = {"RDS": get_url(CH["RDS"]), "DEFAULT": get_url(CH["RDS"])}
LOGOS = {"NHL": "🏒", "NBA": "🏀", "MLB": "⚾", "F1": "🏎️", "UCL": "⚽", "FOOT": "⚽", "MLS": "⚽"}

# =================================================================
# 2. LOGIQUE DE MATCHS
# =================================================================

def get_ranked_games():
    now = datetime.now(pytz.utc)
    all_games = []
    leagues = [
        ('soccer/uefa.champions', 'UCL'), ('hockey/nhl', 'NHL'),
        ('basketball/nba', 'NBA'), ('baseball/mlb', 'MLB'),
        ('racing/f1', 'F1'), ('soccer/eng.1', 'FOOT'), ('soccer/fra.1', 'FOOT')
    ]
    
    for path, sport_key in leagues:
        for i in range(2):
            try:
                d = (now + timedelta(days=i)).strftime("%Y%m%d")
                r = requests.get(f"https://site.api.espn.com/apis/site/v2/sports/{path}/scoreboard?dates={d}", timeout=5).json()
                for e in r.get('events', []):
                    title = e['name'].replace(" at ", " @ ")
                    # On récupère les chaînes (networks)
                    networks = []
                    for comp in e.get('competitions', []):
                        for broadcast in comp.get('geoBroadcasts', []):
                            net_name = broadcast.get('media', {}).get('shortName', '')
                            if net_name: networks.append(net_name.upper())
                    
                    score = P_STD
                    if any(x in title.upper() for x in ULTRA_TEAMS): score = P_ULTRA
                    elif sport_key in ['UCL', 'F1']: score = P_HIGH
                    
                    # URL logic
                    url = MAPPING["DEFAULT"]
                    found_net = "NONE"
                    if sport_key == 'UCL': 
                        url, found_net = get_url(CH["DAZN1"]), "AUTO-DAZN"
                    
                    # Si on trouve une chaîne connue dans les networks
                    for n in networks:
                        if "RDS" in n: url, found_net = get_url(CH["RDS"]), n
                        elif "TVAS" in n: url, found_net = get_url(CH["TVAS"]), n
                        elif "DAZN" in n: url, found_net = get_url(CH["DAZN1"]), n

                    all_games.append({
                        'sport': sport_key, 'title': title, 'score': score, 'id': e['id'],
                        'start_dt': datetime.strptime(e['date'].replace('Z', ''), "%Y-%m-%dT%H:%M").replace(tzinfo=pytz.utc),
                        'url': url, 'nets': networks, 'chosen_net': found_net
                    })
            except: continue
    return sorted(all_games, key=lambda x: (-x['score'], x['start_dt']))

def assign_grid():
    ranked = get_ranked_games()
    grid = {i: [] for i in range(1, 6)}
    slots = {i: [] for i in range(1, 6)}
    assigned_ids = set()

    for g in ranked:
        if g['id'] in assigned_ids: continue
        s, e = g['start_dt'] - timedelta(minutes=45), g['start_dt'] + timedelta(hours=4)
        for i in range(1, 6):
            if not any(not (e <= os or s >= oe) for os, oe in slots[i]):
                slots[i].append((s, e))
                grid[i].append(g)
                assigned_ids.add(g['id'])
                break
    return grid

# =================================================================
# 3. ROUTES
# =================================================================

@app.route('/')
def home(): return "Debug Mode Active - Check EPG for Networks"

@app.route('/nhl-live/<ch>')
def live(ch):
    try:
        now = datetime.now(pytz.utc)
        matches = assign_grid().get(int(ch), [])
        match = next((m for m in matches if (m['start_dt'] - timedelta(minutes=45)) <= now <= (m['start_dt'] + timedelta(hours=4))), None)
        return redirect(match['url'] if match else MAPPING["DEFAULT"], code=302)
    except: return redirect(MAPPING["DEFAULT"])

@app.route('/playlist.m3u')
def playlist():
    host = request.host_url.rstrip('/')
    return Response(f"#EXTM3U\n" + "\n".join([f'#EXTINF:-1 tvg-id="MULTI{i}", MULTI {i}\n{host}/nhl-live/{i}' for i in range(1, 6)]), mimetype='text/plain')

@app.route('/epg.xml')
def epg():
    grid = assign_grid()
    xml = ['<?xml version="1.0" encoding="UTF-8"?><tv>']
    for i in range(1, 6):
        cid = f"MULTI{i}"
        xml.append(f'<channel id="{cid}"><display-name>MULTI {i}</display-name></channel>')
        for m in sorted(grid[i], key=lambda x: x['start_dt']):
            s, logo = m['start_dt'], LOGOS.get(m['sport'], "📺")
            net_list = ",".join(m['nets']) if m['nets'] else "N/A"
            # Titre enrichi : [Réseaux trouvés] -> Choix final
            display_title = f"{logo} {m['title']} [{net_list}] → {m['chosen_net']}"
            
            xml.append(f'<programme start="{(s-timedelta(minutes=30)).strftime("%Y%m%d%H%M%S")} +0000" stop="{s.strftime("%Y%m%d%H%M%S")} +0000" channel="{cid}"><title lang="fr">PRE: {display_title}</title></programme>')
            xml.append(f'<programme start="{s.strftime("%Y%m%d%H%M%S")} +0000" stop="{(s+timedelta(hours=3, minutes=30)).strftime("%Y%m%d%H%M%S")} +0000" channel="{cid}"><title lang="fr">{display_title}</title></programme>')
    xml.append('</tv>')
    return Response("\n".join(xml), mimetype='application/xml')
            
