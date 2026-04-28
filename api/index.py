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

ULTRA_PRIORITY = ["MTL"]
SECONDARY_FAVORITES = ["COL", "BUF", "UTA", "EDM"]

CH = {
    "RDS": "184813", "RDS2": "184814", "RDSInfo": "184815",
    "TVASports": "184811", "TVASports2": "184812",
    "SNEast": "71518", "SNWest": "71521", "SNPacific": "71520",
    "SN1": "71519", "SN4K": "157674", "SNOne4K": "157675"
}

def get_url(cid):
    return f"http://{BASE_DOMAIN}/{USER}/{PASS}/{cid}.ts"

MAPPING = {
    "RDS": get_url(CH["RDS"]), "RDS2": get_url(CH["RDS2"]),
    "SN": get_url(CH["SNEast"]), "SNE": get_url(CH["SNEast"]),
    "SNW": get_url(CH["SNWest"]), "SNP": get_url(CH["SNPacific"]),
    "SN1": get_url(CH["SN1"]), "TVAS": get_url(CH["TVASports"]),
    "TVAS2": get_url(CH["TVASports2"]), "DEFAULT": get_url(CH["RDS"])
}

# =================================================================
# 2. LOGIQUE DE PLACEMENT (SLOT MAPPING)
# =================================================================

def assign_channels(ranked_games):
    """
    Répartit les matchs sur 5 canaux sans chevauchement.
    Retourne un dict : { canal_num: [liste_de_matchs] }
    """
    channels_data = {i: [] for i in range(1, 6)}
    # Slots d'occupation pour valider les collisions (start, end)
    occupation_slots = {i: [] for i in range(1, 6)}
    
    for item in ranked_games:
        g = item['game']
        start_utc = datetime.strptime(g['startTimeUTC'].replace('Z', ''), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=pytz.utc)
        # On réserve 3h15 pour laisser le temps au match de finir
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

def get_custom_desc(g):
    home, away = g['homeTeam']['abbrev'], g['awayTeam']['abbrev']
    if home == "MTL" or away == "MTL": return "Diffusion prioritaire NHL pour MONTRÉAL"
    fav = next((team for team in [home, away] if team in SECONDARY_FAVORITES), None)
    return f"Diffusion NHL {fav}" if fav else "Diffusion NHL"

def get_ranked_games():
    start_date = datetime.now()
    combined_games = []
    for i in range(4):
        date_str = (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
        url = f"https://api-web.nhle.com/v1/schedule/{date_str}"
        try:
            r = requests.get(url, timeout=5)
            data = r.json()
            for day in data.get('gameWeek', []):
                if day.get('date') == date_str:
                    combined_games.extend(day.get('games', []))
        except: continue

    ranked = []
    seen = set()
    for g in combined_games:
        gid = g.get('id')
        if gid in seen or g.get('gameState') == "OFF": continue
        seen.add(gid)
        h, a = g['homeTeam']['abbrev'], g['awayTeam']['abbrev']
        score = 2000 if (h=="MTL" or a=="MTL") else (1000 if (h in SECONDARY_FAVORITES or a in SECONDARY_FAVORITES) else 10)
        
        tv = [t['network'] for t in g.get('tvBroadcasts', []) if t['countryCode'] == 'CA']
        best_url, b_bonus = MAPPING["DEFAULT"], -1
        for net in tv:
            k = next((key for key in MAPPING if key in net), None)
            if not k: continue
            bonus = 500 if (score == 2000 and "RDS" in net) else (300 if "SN" in net else 50)
            if bonus > b_bonus: b_bonus, best_url = bonus, MAPPING[k]
        
        ranked.append({'game': g, 'url': best_url, 'total_score': score + b_bonus})

    ranked.sort(key=lambda x: (-x['total_score'], x['game']['startTimeUTC']))
    return ranked

# =================================================================
# 3. ROUTES
# =================================================================

@app.route('/nhl-live/<int:ch_num>')
def redirect_channel(ch_num):
    """Redirection dynamique vers le match ACTUELLEMENT diffusé sur le canal X"""
    ranked = get_ranked_games()
    grid = assign_channels(ranked)
    
    now = datetime.utcnow().replace(tzinfo=pytz.utc)
    match_found = None
    
    for item in grid.get(ch_num, []):
        g = item['game']
        start_utc = datetime.strptime(g['startTimeUTC'].replace('Z', ''), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=pytz.utc)
        # On active le stream 30 min avant et on le laisse 3h après
        if (now >= start_utc - timedelta(minutes=30)) and (now <= start_utc + timedelta(hours=3, minutes=30)):
            match_found = item
            break
            
    url = match_found['url'] if match_found else MAPPING["DEFAULT"]
    res = make_response(redirect(url, code=302))
    res.headers['User-Agent'] = 'IPTVSmarters/1.0.3'
    return res

@app.route('/playlist.m3u')
def generate_m3u():
    ranked = get_ranked_games()
    grid = assign_channels(ranked)
    m3u = ["#EXTM3U"]
    
    for i in range(1, 6):
        # On cherche le match "courant" pour le label, sinon le prochain
        now = datetime.utcnow().replace(tzinfo=pytz.utc)
        current_game = None
        for item in grid[i]:
            start = datetime.strptime(item['game']['startTimeUTC'].replace('Z', ''), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=pytz.utc)
            if now <= start + timedelta(hours=3):
                current_game = item
                break
        
        label = f"({current_game['game']['awayTeam']['abbrev']} @ {current_game['game']['homeTeam']['abbrev']})" if current_game else "(En attente)"
        m3u.append(f'#EXTINF:-1 tvg-id="NHL.Live.{i}" tvg-name="NHL LIVE {i}" group-title="Hockey", NHL LIVE {i} {label}')
        m3u.append(f"http://{request.host}/nhl-live/{i}")
    
    return Response("\n".join(m3u), mimetype='text/plain')

@app.route('/epg.xml')
def generate_epg():
    ranked = get_ranked_games()
    grid = assign_channels(ranked)
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<tv>']
    for i in range(1, 6): xml.append(f'<channel id="NHL.Live.{i}"><display-name>NHL LIVE {i}</display-name></channel>')
    
    tz_mtl = pytz.timezone('America/Montreal')
    for ch_num, matches in grid.items():
        for item in matches:
            g = item['game']
            start_utc = datetime.strptime(g['startTimeUTC'].replace('Z', ''), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=pytz.utc)
            stop_utc = start_utc + timedelta(hours=2, minutes=30)
            p_start = start_utc - timedelta(minutes=30)
            
            # Pregame
            xml.append(f'<programme start="{p_start.strftime("%Y%m%d%H%M%S")} +0000" stop="{start_utc.strftime("%Y%m%d%H%M%S")} +0000" channel="NHL.Live.{ch_num}">')
            xml.append(f'  <title lang="fr">🏒 PREGAME : {g["awayTeam"]["abbrev"]} @ {g["homeTeam"]["abbrev"]}</title>')
            xml.append(f'  <desc lang="fr">Début à {start_utc.astimezone(tz_mtl).strftime("%H:%M")}.</desc>')
            xml.append('</programme>')
            # Match
            xml.append(f'<programme start="{start_utc.strftime("%Y%m%d%H%M%S")} +0000" stop="{stop_utc.strftime("%Y%m%d%H%M%S")} +0000" channel="NHL.Live.{ch_num}">')
            xml.append(f'  <title lang="fr">{g["awayTeam"]["abbrev"]} @ {g["homeTeam"]["abbrev"]}</title>')
            xml.append(f'  <desc lang="fr">{get_custom_desc(g)}</desc>')
            xml.append('</programme>')

    xml.append('</tv>')
    return Response("\n".join(xml), mimetype='text/xml')
    
