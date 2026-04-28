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
ULTRA_TEAMS = ["MTL", "CAN", "CANADIENS", "MONTREAL", "CF MONTRÉAL", "TOR", "BLUE JAYS", "RAPTORS", "PSG", "MCI", "F1"]

CH = {
    "RDS": "184813", "RDS2": "184814", "TVAS": "184811", "TVAS2": "184812",
    "SNE": "71518", "SN1": "71519", "TSN1": "71234", "OneSoccer": "18435", 
    "SkyF1": "71300", "CanalPlus": "49943", "BEIN1FR": "157279", "DAZN1": "176642"
}
# Génération DAZN 2-10
for i in range(2, 11): CH[f"DAZN{i}"] = str(176642 + (i - 1))

def get_url(cid):
    return f"http://{BASE_DOMAIN}/{USER}/{PASS}/{cid}.ts"

MAPPING = {"RDS": get_url(CH["RDS"]), "DEFAULT": get_url(CH["RDS"])}

# =================================================================
# 2. LOGIQUE DE RÉCUPÉRATION
# =================================================================

def get_ranked_games():
    now = datetime.now(pytz.utc)
    all_games = []
    
    # On surveille les ligues majeures
    leagues = [
        ('soccer/uefa.champions', 'UCL'), 
        ('hockey/nhl', 'NHL'),
        ('basketball/nba', 'NBA'),
        ('racing/f1', 'F1')
    ]
    
    for path, sport_key in leagues:
        try:
            r = requests.get(f"https://site.api.espn.com/apis/site/v2/sports/{path}/scoreboard", timeout=5).json()
            for e in r.get('events', []):
                title = e['name']
                title_up = title.upper()
                
                # Calcul du score
                score = P_STD
                if any(x in title_up for x in ULTRA_TEAMS): score = P_ULTRA
                elif sport_key in ['UCL', 'F1']: score = P_HIGH
                
                # URL par défaut selon le sport (Correction pour le Bayern/UCL)
                if sport_key == 'UCL':
                    default_url = get_url(CH["DAZN1"])
                elif sport_key == 'F1':
                    default_url = get_url(CH["SkyF1"])
                else:
                    default_url = MAPPING["DEFAULT"]

                all_games.append({
                    'sport': sport_key,
                    'title': title.replace(" at ", " @ "),
                    'score': score,
                    'start_dt': datetime.strptime(e['date'].replace('Z', ''), "%Y-%m-%dT%H:%M").replace(tzinfo=pytz.utc),
                    'url': default_url,
                    'id': e['id']
                })
        except: continue
        
    return sorted(all_games, key=lambda x: (-x['score'], x['start_dt']))

def assign_grid():
    games = get_ranked_games()
    grid = {i: None for i in range(1, 6)}
    now = datetime.now(pytz.utc)
    
    idx = 1
    for g in games:
        if idx > 5: break
        # Match actif ? (45 min avant à 4h après)
        if (g['start_dt'] - timedelta(minutes=45)) <= now <= (g['start_dt'] + timedelta(hours=4)):
            grid[idx] = g
            idx += 1
    return grid

# =================================================================
# 3. ROUTES
# =================================================================

@app.route('/')
def home():
    return "Serveur Multi-Sport Actif"

@app.route('/nhl-live/<ch>')
def live(ch):
    try:
        match = assign_grid().get(int(ch))
        url = match['url'] if match else MAPPING["DEFAULT"]
        res = make_response(redirect(url, code=302))
        res.headers['User-Agent'] = 'IPTVSmarters/1.0.3'
        return res
    except:
        return redirect(MAPPING["DEFAULT"])

@app.route('/playlist.m3u')
def playlist():
    host = request.host_url.rstrip('/')
    m3u = ["#EXTM3U"]
    for i in range(1, 6):
        m3u.append(f'#EXTINF:-1 tvg-id="MULTI{i}" group-title="LIVE SPORTS", MULTI SPORT {i}')
        m3u.append(f"{host}/nhl-live/{i}")
    return Response("\n".join(m3u), mimetype='text/plain')

@app.route('/epg.xml')
def epg():
    grid = assign_grid()
    xml = ['<?xml version="1.0" encoding="UTF-8"?><tv>']
    for i in range(1, 6):
        cid = f"MULTI{i}"
        xml.append(f'<channel id="{cid}"><display-name>MULTI {i}</display-name></channel>')
        m = grid[i]
        if m:
            s = m['start_dt']
            xml.append(f'<programme start="{s.strftime("%Y%m%d%H%M%S")} +0000" stop="{(s+timedelta(hours=3)).strftime("%Y%m%d%H%M%S")} +0000" channel="{cid}"><title lang="fr">{m["title"]}</title></programme>')
    xml.append('</tv>')
    return Response("\n".join(xml), mimetype='application/xml')

if __name__ == '__main__':
    app.run()
    
