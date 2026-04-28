from flask import Flask, Response, request, redirect, make_response
import requests
from datetime import datetime, timedelta
import pytz
import re

app = Flask(__name__)

# --- CONFIG ---
USER, PASS, BASE_DOMAIN = "tDcJnv4jMM", "2khBtbUZuV", "omegatv.live:80"
P_ULTRA, P_HIGH, P_STD = 2500, 1200, 50
ULTRA_TEAMS = ["MTL", "CAN", "CANADIENS", "MONTREAL", "CF MONTRÉAL", "TOR", "BLUE JAYS", "RAPTORS", "PSG", "MCI"]

CH = {"RDS": "184813", "RDS2": "184814", "TVAS": "184811", "TVAS2": "184812", "SNE": "71518", "SN1": "71519", "TSN1": "71234", "OneSoccer": "18435", "SkyF1": "71300", "CanalPlus": "49943", "BEIN1FR": "157279"}
for i in range(1, 101): CH[f"DAZN{i}"] = str(176642 + (i - 1))
for i in range(1, 51):  CH[f"MLS{i}"] = str(175474 + (i - 1))

def get_url(cid): return f"http://{BASE_DOMAIN}/{USER}/{PASS}/{cid}.ts"

MAPPING = {"RDS": get_url(CH["RDS"]), "DEFAULT": get_url(CH["RDS"]), "DAZN1": get_url(CH["DAZN1"]), "SKY": get_url(CH["SkyF1"])}

# --- LOGIQUE ---
def get_ranked_games():
    now = datetime.now(pytz.utc)
    all_games = []
    # Focus sur UCL et NHL pour le test
    leagues = [('soccer/uefa.champions', 'UCL'), ('hockey/nhl', 'NHL')]
    for path, sport in leagues:
        try:
            r = requests.get(f"https://site.api.espn.com/apis/site/v2/sports/{path}/scoreboard", timeout=5).json()
            for e in r.get('events', []):
                all_games.append({
                    'sport': sport, 'title': e['name'], 'score': P_ULTRA if any(x in e['name'].upper() for x in ULTRA_TEAMS) else P_HIGH,
                    'id': e['id'], 'start_dt': datetime.strptime(e['date'].replace('Z', ''), "%Y-%m-%dT%H:%M").replace(tzinfo=pytz.utc),
                    'url': get_url(CH["DAZN1"]) if sport == 'UCL' else get_url(CH["RDS"])
                })
        except: continue
    return sorted(all_games, key=lambda x: (-x['score'], x['start_dt']))

def assign():
    games = get_ranked_games()
    grid = {i: None for i in range(1, 6)}
    now = datetime.now(pytz.utc)
    idx = 1
    for g in games:
        if idx > 5: break
        if (g['start_dt'] - timedelta(minutes=45)) <= now <= (g['start_dt'] + timedelta(hours=4)):
            grid[idx] = g
            idx += 1
    return grid

# --- ROUTES ---
@app.route('/')
def home(): return "Serveur Actif"

@app.route('/nhl-live/<ch>')
def live(ch):
    try:
        match = assign().get(int(ch))
        url = match['url'] if match else MAPPING["DEFAULT"]
        res = make_response(redirect(url, code=302))
        res.headers['User-Agent'] = 'IPTVSmarters/1.0.3'
        return res
    except: return redirect(MAPPING["DEFAULT"])

@app.route('/playlist.m3u')
def playlist():
    host = request.host_url.rstrip('/')
    m3u = ["#EXTM3U"]
    for i in range(1, 6):
        m3u.append(f'#EXTINF:-1 tvg-id="NHL{i}", MULTI {i}\n{host}/nhl-live/{i}')
    return Response("\n".join(m3u), mimetype='text/plain')

@app.route('/epg.xml')
def epg():
    xml = ['<?xml version="1.0" encoding="UTF-8"?><tv>']
    for i in range(1, 6):
        xml.append(f'<channel id="NHL{i}"><display-name>MULTI {i}</display-name></channel>')
    xml.append('</tv>')
    return Response("\n".join(xml), mimetype='application/xml')
    
