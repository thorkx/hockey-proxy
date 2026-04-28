from flask import Flask, Response, request, redirect, make_response
import requests
from datetime import datetime, timedelta
import pytz
import re

app = Flask(__name__)

# =================================================================
# 1. CONFIGURATION
# =================================================================
USER = "tDcJnv4jMM"
PASS = "2khBtbUZuV"
BASE_DOMAIN = "omegatv.live:80"

P_ULTRA, P_HIGH, P_STD = 2500, 1200, 50

ULTRA_TEAMS = [
    "MTL", "CAN", "CANADIENS", "MONTREAL", "CF MONTRÉAL", 
    "TOR", "BLUE JAYS", "RAPTORS", "VAN", "WHITECAPS",
    "MCI", "MAN CITY", "MANCHESTER CITY", "PSG", "PARIS SAINT-GERMAIN",
    "BOL", "BOLOGNA", "BOLOGNE", "WXM", "WREXHAM",
    "F1", "CPL", "NORTH"
]

FAV_TEAMS = ["COL", "BUF", "UTA", "EDM", "LAL", "GSW", "BOS", "NYY", "LAD"]

CH = {
    "RDS": "184813", "RDS2": "184814", "TVAS": "184811", "TVAS2": "184812",
    "SNE": "71518", "SNW": "71521", "SNP": "71520", "SN1": "71519", "SN360": "71522",
    "TSN1": "71234", "TSN2": "71235", "TSN3": "71236", "TSN4": "71237", "TSN5": "71238",
    "OneSoccer": "18435", "SkyF1": "71300", "CanalPlus": "49943",
    "BEIN1FR": "157279", "BEIN2FR": "157282"
}

for i in range(1, 101): CH[f"DAZN{i}"] = str(176642 + (i - 1))
for i in range(1, 51):  CH[f"MLS{i}"] = str(175474 + (i - 1))

def get_url(cid):
    return f"http://{BASE_DOMAIN}/{USER}/{PASS}/{cid}.ts"

MAPPING = {
    "RDS": get_url(CH["RDS"]), "TVAS": get_url(CH["TVAS"]), "SN": get_url(CH["SNE"]),
    "TSN": get_url(CH["TSN1"]), "ONES": get_url(CH["OneSoccer"]), "SKY": get_url(CH["SkyF1"]), 
    "CANAL": get_url(CH["CanalPlus"]), "BEIN": get_url(CH["BEIN1FR"]), "DAZN": get_url(CH["DAZN1"]), 
    "MLS": get_url(CH["MLS1"]), "APPLE": get_url(CH["MLS1"]), "DEFAULT": get_url(CH["RDS"])
}

# =================================================================
# 2. LOGIQUE
# =================================================================

def assign_channels(ranked_games):
    grid = {i: [] for i in range(1, 6)}
    slots = {i: [] for i in range(1, 6)}
    assigned_match_ids = set() 

    for item in ranked_games:
        if item['id'] in assigned_match_ids: continue
        # Fenêtre de blocage : 30 min avant, 3h30 après
        s, e = item['start_dt'] - timedelta(minutes=30), item['start_dt'] + timedelta(hours=3, minutes=30)
        for i in range(1, 6):
            if not any(not (e <= os or s >= oe) for os, oe in slots[i]):
                slots[i].append((s, e))
                grid[i].append(item)
                assigned_match_ids.add(item['id'])
                break
    return grid

def get_ranked_games():
    now = datetime.now(pytz.utc)
    all_games = []
    
    # 2.1 NHL
    for i in range(3):
        d = (now + timedelta(days=i)).strftime("%Y-%m-%d")
        try:
            r = requests.get(f"https://api-web.nhle.com/v1/schedule/{d}", timeout=5).json()
            for day in r.get('gameWeek', []):
                for g in day.get('games', []):
                    if g.get('gameState') == "OFF": continue
                    h_disp, a_disp = f"{g['homeTeam']['placeName']['default']} {g['homeTeam']['commonName']['default']}", f"{g['awayTeam']['placeName']['default']} {g['awayTeam']['commonName']['default']}"
                    h_u, a_u, h_ab, a_ab = h_disp.upper(), a_disp.upper(), g['homeTeam']['abbrev'].upper(), g['awayTeam']['abbrev'].upper()
                    
                    score = P_STD
                    if any(x in [h_ab, a_ab] or x in h_u or x in a_u for x in ULTRA_TEAMS): score = P_ULTRA
                    elif any(x in [h_ab, a_ab] for x in FAV_TEAMS): score = P_HIGH
                        
                    all_games.append({
                        'sport': 'NHL', 'title': f"{a_disp} @ {h_disp}", 'score': score, 'id': f"nhl_{g['id']}",
                        'start_dt': datetime.strptime(g['startTimeUTC'].replace('Z', ''), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=pytz.utc),
                        'networks': [t['network'] for t in g.get('tvBroadcasts', []) if t['countryCode'] == 'CA']
                    })
        except: continue

    # 2.2 ESPN
    leagues = [('basketball/nba', 'NBA'), ('baseball/mlb', 'MLB'), ('racing/f1', 'F1'), 
               ('soccer/usa.1', 'FOOT'), ('soccer/can.1', 'FOOT'), ('soccer/uefa.champions', 'FOOT'), 
               ('soccer/eng.1', 'FOOT'), ('soccer/fra.1', 'FOOT'), ('soccer/esp.1', 'FOOT'), ('soccer/ita.1', 'FOOT')]
    for path, sport_key in leagues:
        for i in range(3):
            try:
                d = (now + timedelta(days=i)).strftime("%Y%m%d")
                r = requests.get(f"https://site.api.espn.com/apis/site/v2/sports/{path}/scoreboard?dates={d}", timeout=5).json()
                for e in r.get('events', []):
                    title_up = e['name'].upper()
                    teams = [c['team']['abbreviation'].upper() for c in e['competitions'][0]['competitors']]
                    score = P_STD
                    if any(t in teams for t in ULTRA_TEAMS) or any(fav in title_up for fav in ULTRA_TEAMS): score = P_ULTRA
                    elif sport_key == 'F1' or 'champions' in path: score = P_HIGH
                    elif any(t in teams for t in FAV_TEAMS): score = P_HIGH
                    
                    all_games.append({
                        'sport': sport_key, 'title': e['name'].replace(" at ", " @ "), 'score': score, 'id': f"espn_{e['id']}",
                        'start_dt': datetime.strptime(e['date'].replace('Z', ''), "%Y-%m-%dT%H:%M").replace(tzinfo=pytz.utc),
                        'networks': [b.get('media', {}).get('shortName', '') for b in e['competitions'][0].get('geoBroadcasts', [])]
                    })
            except: continue

    # 2.3 MAPPING
    ranked = []
    for item in all_games:
        best_url, best_bonus = MAPPING["DEFAULT"], -1
        for net in item['networks']:
            net_u = net.upper()
            mk = next((k for k in sorted(MAPPING.keys(), key=len, reverse=True) if k in net_u), None)
            bonus, current_url = 0, MAPPING["DEFAULT"]
            if mk:
                if any(x in mk for x in ["CANAL", "RDS", "TVAS", "ONES"]): bonus, current_url = 950, MAPPING[mk]
                elif "BEIN" in mk:
                    bonus = 750
                    if "FR" in net_u: bonus, current_url = 900, get_url(CH["BEIN1FR"])
                    else: current_url = MAPPING[mk]
                elif "SKY" in mk: bonus, current_url = 850, MAPPING[mk]
                elif any(x in mk for x in ["DAZN", "MLS", "APPLE"]):
                    bonus, current_url = 600, MAPPING[mk]
                    num = re.search(r'\d+', net_u)
                    if num and f"{'DAZN' if 'DAZN' in net_u else 'MLS'}{num.group()}" in CH:
                        current_url, bonus = get_url(CH[f"{'DAZN' if 'DAZN' in net_u else 'MLS'}{num.group()}"]), bonus + 50
                else: bonus, current_url = 400, MAPPING[mk]
            if bonus > best_bonus: best_bonus, best_url = bonus, current_url
        item['url'], item['total_score'] = best_url, item['score'] + best_bonus
        ranked.append(item)
    return sorted(ranked, key=lambda x: (-x['total_score'], x['start_dt']))

# =================================================================
# 3. ROUTES
# =================================================================

@app.route('/nhl-live/<int:ch_num>')
def redirect_channel(ch_num):
    # On force le calcul en UTC pour éviter les erreurs de serveur
    utc = pytz.UTC
    now = datetime.now(utc)
    
    ranked = get_ranked_games()
    grid = assign_channels(ranked)
    
    match = None
    # On parcourt les matchs assignés à ce poste
    for m in grid.get(ch_num, []):
        # On s'assure que le temps du match est bien en UTC pour la comparaison
        match_start = m['start_dt'].astimezone(utc)
        
        # Fenêtre : On commence 45 min avant et on finit 4h après le début
        start_window = match_start - timedelta(minutes=45)
        end_window = match_start + timedelta(hours=4)
        
        if start_window <= now <= end_window:
            match = m
            break
    
    if match:
        target_url = match['url']
        print(f"MATCH TROUVÉ : {match['title']} sur le poste {ch_num}")
    else:
        target_url = MAPPING["DEFAULT"]
        print(f"AUCUN MATCH ACTIF sur le poste {ch_num}, redirection vers RDS.")
    
    res = make_response(redirect(target_url, code=302))
    res.headers['User-Agent'] = 'IPTVSmarters/1.0.3'
    return res
    


@app.route('/playlist.m3u')
def generate_m3u():
    m3u = ["#EXTM3U"]
    for i in range(1, 6):
        m3u.append(f'#EXTINF:-1 tvg-id="NHL.Live.{i}" group-title="LIVE SPORTS", MULTI SPORT {i}')
        m3u.append(f"http://{request.host}/nhl-live/{i}")
    return Response("\n".join(m3u), mimetype='text/plain')

@app.route('/epg.xml')
def generate_epg():
    grid = assign_channels(get_ranked_games())
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<tv>']
    logos = {"NHL": "🏒", "NBA": "🏀", "MLB": "⚾", "F1": "🏎️", "FOOT": "⚽"}
    for i in range(1, 6):
        cid = f"NHL.Live.{i}"
        xml.append(f'<channel id="{cid}"><display-name>MULTI SPORT {i}</display-name></channel>')
        for item in sorted(grid[i], key=lambda x: x['start_dt']):
            s, logo = item['start_dt'], logos.get(item['sport'], "📺")
            xml.append(f'<programme start="{(s-timedelta(minutes=30)).strftime("%Y%m%d%H%M%S")} +0000" stop="{s.strftime("%Y%m%d%H%M%S")} +0000" channel="{cid}"><title lang="fr">{logo} PRE : {item["title"]}</title></programme>')
            xml.append(f'<programme start="{s.strftime("%Y%m%d%H%M%S")} +0000" stop="{(s+timedelta(hours=3, minutes=15)).strftime("%Y%m%d%H%M%S")} +0000" channel="{cid}"><title lang="fr">{logo} {item["title"]}</title></programme>')
    xml.append('</tv>')
    return Response("\n".join(xml), mimetype='application/xml')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
                
