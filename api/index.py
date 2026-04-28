from flask import Flask, Response, request, redirect, make_response
import requests
from datetime import datetime, timedelta
import pytz

app = Flask(__name__)

# =================================================================
# 1. CONFIGURATION (TES ACCÈS OMEGATV)
# =================================================================
USER = "tDcJnv4jMM"
PASS = "2khBtbUZuV"
BASE_DOMAIN = "omegatv.live:80"
BASE_URL = "https://thorkx-hockey-proxy.vercel.app"

# Priorités
ULTRA_NHL = ["MTL"]
ULTRA_NBA = ["TOR"]
ULTRA_MLB = ["TOR"]
ULTRA_F1 = ["F1"]

FAV_NHL = ["COL", "BUF", "UTA", "EDM"]
FAV_NBA = ["LAL", "GSW", "BOS"]
FAV_MLB = ["NYY", "LAD", "BOS"]

CH = {
    "RDS": "184813", "RDS2": "184814", "TVASports": "184811", "TVASports2": "184812",
    "SNEast": "71518", "SNWest": "71521", "SNPacific": "71520", "SN1": "71519", "SN360": "71522",
    "TSN1": "71234", "TSN2": "71235", "TSN3": "71236", "TSN4": "71237", "TSN5": "71238",
    "SkyF1": "71300" 
}

def get_url(cid):
    return f"http://{BASE_DOMAIN}/{USER}/{PASS}/{cid}.ts"

MAPPING = {
    "RDS": get_url(CH["RDS"]), "RDS2": get_url(CH["RDS2"]),
    "TVAS": get_url(CH["TVASports"]), "TVAS2": get_url(CH["TVASports2"]),
    "SN": get_url(CH["SNEast"]), "SN1": get_url(CH["SN1"]), "SN360": get_url(CH["SN360"]),
    "TSN1": get_url(CH["TSN1"]), "TSN2": get_url(CH["TSN2"]), "TSN3": get_url(CH["TSN3"]), 
    "TSN4": get_url(CH["TSN4"]), "TSN5": get_url(CH["TSN5"]), "TSN": get_url(CH["TSN1"]),
    "SKY": get_url(CH["SkyF1"]), "DEFAULT": get_url(CH["RDS"])
}

# =================================================================
# 2. LOGIQUE DE RANKING
# =================================================================

def assign_channels(ranked_games):
    channels_data = {i: [] for i in range(1, 6)}
    occupation_slots = {i: [] for i in range(1, 6)}
    for item in ranked_games:
        start_utc = item['start_dt']
        stop_utc = start_utc + timedelta(hours=3, minutes=15)
        collision_start = start_utc - timedelta(minutes=30)
        for ch_num in range(1, 6):
            has_collision = False
            for occ_start, occ_stop in occupation_slots[ch_num]:
                if not (stop_utc <= occ_start or collision_start >= occ_stop):
                    has_collision = True
                    break
            if not has_collision:
                occupation_slots[ch_num].append((collision_start, stop_utc))
                channels_data[ch_num].append(item)
                break
    return channels_data

def get_ranked_games():
    now = datetime.now(pytz.utc)
    all_raw_games = []
    
    # --- FETCH NHL ---
    for i in range(3):
        d_str = (now + timedelta(days=i)).strftime("%Y-%m-%d")
        try:
            r = requests.get(f"https://api-web.nhle.com/v1/schedule/{d_str}", timeout=5).json()
            for day in r.get('gameWeek', []):
                if day['date'] == d_str:
                    for g in day.get('games', []):
                        if g.get('gameState') == "OFF": continue
                        h, a = g['homeTeam']['abbrev'], g['awayTeam']['abbrev']
                        score = 2000 if (h in ULTRA_NHL or a in ULTRA_NHL) else (1000 if (h in FAV_NHL or a in FAV_NHL) else 10)
                        all_raw_games.append({
                            'sport': 'NHL', 'title': f"{a} @ {h}", 'start_dt': datetime.strptime(g['startTimeUTC'].replace('Z', ''), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=pytz.utc),
                            'score': score, 'networks': [t['network'] for t in g.get('tvBroadcasts', []) if t['countryCode'] == 'CA'], 'id': f"nhl_{g['id']}"
                        })
        except: continue

    # --- FETCH NBA, MLB, F1 (ESPN) ---
    for sport in ['basketball/nba', 'baseball/mlb', 'racing/f1']:
        for i in range(3):
            try:
                d_str = (now + timedelta(days=i)).strftime("%Y%m%d")
                r = requests.get(f"https://site.api.espn.com/apis/site/v2/sports/{sport}/scoreboard?dates={d_str}", timeout=5).json()
                for event in r.get('events', []):
                    s_key = "NBA" if "nba" in sport else ("MLB" if "mlb" in sport else "F1")
                    title = event['name'] if s_key == "F1" else f"{event['competitions'][0]['competitors'][1]['team']['abbreviation']} @ {event['competitions'][0]['competitors'][0]['team']['abbreviation']}"
                    
                    score = 5
                    if s_key == "F1": score = 1800
                    else:
                        codes = [c['team']['abbreviation'].upper() for c in event['competitions'][0]['competitors']]
                        fav_list = ULTRA_NBA if s_key == "NBA" else ULTRA_MLB
                        if any(c in fav_list for c in codes): score = 2000
                    
                    dt = datetime.strptime(event['date'].replace('Z', ''), "%Y-%m-%dT%H:%M").replace(tzinfo=pytz.utc)
                    all_raw_games.append({
                        'sport': s_key, 'title': title, 'start_dt': dt, 'score': score, 
                        'networks': [b.get('media', {}).get('shortName', '') for b in event['competitions'][0].get('geoBroadcasts', [])], 'id': f"{s_key.lower()}_{event['id']}"
                    })
            except: continue

    # --- RANKING & URL ---
    ranked = []
    for item in all_raw_games:
        best_url, best_bonus = MAPPING["DEFAULT"], -1
        for net in item['networks']:
            net_u = net.upper()
            match_key = next((k for k in sorted(MAPPING.keys(), key=len, reverse=True) if k in net_u), None)
            if not match_key: continue
            
            bonus = 100
            if "RDS" in match_key or "TVAS" in match_key: bonus = 500
            elif "SKY" in match_key: bonus = 800
            elif "SN" in match_key or "TSN" in match_key: bonus = 300
            
            if bonus > best_bonus: best_bonus, best_url = bonus, MAPPING[match_key]
        
        item['url'], item['total_score'] = best_url, item['score'] + best_bonus
        ranked.append(item)

    ranked.sort(key=lambda x: (-x['total_score'], x['start_dt']))
    return ranked

# =================================================================
# 3. ROUTES
# =================================================================

@app.route('/nhl-live/<int:ch_num>')
def redirect_channel(ch_num):
    ranked = get_ranked_games()
    grid = assign_channels(ranked)
    now = datetime.now(pytz.utc)
    match = next((i for i in grid.get(ch_num, []) if i['start_dt'] - timedelta(minutes=30) <= now <= i['start_dt'] + timedelta(hours=3, minutes=30)), None)
    res = make_response(redirect(match['url'] if match else MAPPING["DEFAULT"], code=302))
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
    ranked = get_ranked_games()
    grid = assign_channels(ranked)
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<tv>']
    logos = {"NHL": "🏒", "NBA": "🏀", "MLB": "⚾", "F1": "🏎️"}
    for i in range(1, 6):
        cid = f"NHL.Live.{i}"
        xml.append(f'<channel id="{cid}"><display-name>MULTI SPORT {i}</display-name></channel>')
        for item in grid[i]:
            s = item['start_dt']
            logo = logos.get(item['sport'], "📺")
            xml.append(f'<programme start="{(s-timedelta(minutes=30)).strftime("%Y%m%d%H%M%S")} +0000" stop="{s.strftime("%Y%m%d%H%M%S")} +0000" channel="{cid}">')
            xml.append(f'<title lang="fr">{logo} PRE : {item["title"]}</title></programme>')
            xml.append(f'<programme start="{s.strftime("%Y%m%d%H%M%S")} +0000" stop="{(s+timedelta(hours=3)).strftime("%Y%m%d%H%M%S")} +0000" channel="{cid}">')
            xml.append(f'<title lang="fr">{logo} {item["title"]}</title></programme>')
    xml.append('</tv>')
    return Response("\n".join(xml), mimetype='application/xml')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
