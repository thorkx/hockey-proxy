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

# Tes listes d'équipes (utilisées pour le tri ET les descriptions)
ULTRA_PRIORITY = ["MTL"]
SECONDARY_FAVORITES = ["COL", "BUF", "UTA", "TOR", "EDM", "BOS"]

CH = {
    "RDS": "184813", "RDS2": "184814", "RDSInfo": "184815",
    "TVASports": "184811", "TVASports2": "184812",
    "SNEast": "71518", "SNWest": "71521", "SNPacific": "71520",
    "SN1": "71519", "SN4K": "157674", "SNOne4K": "157675"
}

def get_url(cid):
    return f"http://{BASE_DOMAIN}/{USER}/{PASS}/{cid}.ts"

MAPPING = {
    "RDS": get_url(CH["RDS"]),
    "RDS2": get_url(CH["RDS2"]),
    "SN": get_url(CH["SNEast"]),
    "SNE": get_url(CH["SNEast"]),
    "SNW": get_url(CH["SNWest"]),
    "SNP": get_url(CH["SNPacific"]),
    "SN1": get_url(CH["SN1"]),
    "TVAS": get_url(CH["TVASports"]),
    "TVAS2": get_url(CH["TVASports2"]),
    "DEFAULT": get_url(CH["RDS"])
}

# =================================================================
# 2. LOGIQUE MÉTIER
# =================================================================

def get_custom_desc(g):
    """Génère la description EPG basée sur les priorités réelles."""
    home, away = g['homeTeam']['abbrev'], g['awayTeam']['abbrev']
    
    if home == "MTL" or away == "MTL": 
        return "Diffusion prioritaire NHL pour MONTRÉAL"
    
    # On vérifie si l'une des équipes est dans tes favoris secondaires
    fav = next((team for team in [home, away] if team in SECONDARY_FAVORITES), None)
    if fav:
        return f"Diffusion prioritaire NHL pour {fav}"
        
    return "Diffusion NHL"

def get_ranked_games():
    """Récupère et trie les matchs : Score (desc) puis Heure (asc)."""
    start_date = datetime.now()
    combined_games = []
    
    for i in range(4):
        current_date_str = (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
        url = f"https://api-web.nhle.com/v1/schedule/{current_date_str}"
        try:
            r = requests.get(url, timeout=5)
            data = r.json()
            for day in data.get('gameWeek', []):
                if day.get('date') == current_date_str:
                    combined_games.extend(day.get('games', []))
        except:
            continue

    ranked_list = []
    seen_game_ids = set()

    for g in combined_games:
        game_id = g.get('id')
        if game_id in seen_game_ids or g.get('gameState') == "OFF":
            continue
        seen_game_ids.add(game_id)

        home, away = g['homeTeam']['abbrev'], g['awayTeam']['abbrev']
        
        # Calcul du score basé sur les mêmes listes que la description
        score = 0
        if home == "MTL" or away == "MTL":
            score = 2000
        elif home in SECONDARY_FAVORITES or away in SECONDARY_FAVORITES:
            score = 1000
        else:
            score = 10

        # Bonus diffuseur
        tv_list = [tv['network'] for tv in g.get('tvBroadcasts', []) if tv['countryCode'] == 'CA']
        best_url = MAPPING.get("DEFAULT")
        best_bonus = -1

        for net in tv_list:
            match_key = next((k for k in MAPPING if k in net), None)
            if not match_key: continue
            # RDS est favorisé pour MTL, SN pour le reste
            bonus = 500 if (score == 2000 and "RDS" in net) else (300 if "SN" in net else 50)
            if bonus > best_bonus:
                best_bonus, best_url = bonus, MAPPING[match_key]

        ranked_list.append({
            'game': g,
            'url': best_url,
            'total_score': score + best_bonus
        })

    # TRI : Score élevé d'abord, puis heure la plus tôt
    ranked_list.sort(key=lambda x: (-x['total_score'], x['game']['startTimeUTC']))
    return ranked_list

# =================================================================
# 3. ROUTES FLASK
# =================================================================

@app.route('/nhl-live')
def redirect_to_nhl():
    ranked = get_ranked_games()
    final_url = ranked[0]['url'] if ranked else MAPPING["DEFAULT"]
    response = make_response(redirect(final_url, code=302))
    response.headers['User-Agent'] = 'IPTVSmarters/1.0.3'
    return response

@app.route('/playlist.m3u')
def generate_m3u():
    ranked = get_ranked_games()
    now = datetime.utcnow()
    m3u = ["#EXTM3U"]
    
    active_matches = []
    for item in ranked:
        start_dt = datetime.strptime(item['game']['startTimeUTC'].replace('Z', ''), "%Y-%m-%dT%H:%M:%S")
        if item['game']['gameState'] in ["LIVE", "CRIT"] or now >= (start_dt - timedelta(minutes=30)):
            active_matches.append(item)

    display_count = max(1, len(active_matches))
    for i in range(min(display_count, 5)):
        channel_num = i + 1
        if i < len(active_matches):
            g = active_matches[i]['game']
            url = f"http://{request.host}/nhl-live" if channel_num == 1 else active_matches[i]['url']
            label = f"({g['awayTeam']['abbrev']} @ {g['homeTeam']['abbrev']})"
        else:
            url = MAPPING.get("DEFAULT")
            label = "(En attente)"
            
        m3u.append(f'#EXTINF:-1 tvg-id="NHL.Live.{channel_num}" tvg-name="NHL LIVE {channel_num}" group-title="Hockey", NHL LIVE {channel_num} {label}')
        m3u.append(url)
    
    return Response("\n".join(m3u), mimetype='text/plain')

@app.route('/epg.xml')
def generate_epg():
    ranked = get_ranked_games()
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<tv>']
    for i in range(1, 6):
        xml.append(f'<channel id="NHL.Live.{i}"><display-name>NHL LIVE {i}</display-name></channel>')
    
    now_utc = datetime.utcnow().replace(tzinfo=pytz.utc)
    tz_mtl = pytz.timezone('America/Montreal')

    if ranked:
        # CANAL 1 (MASTER)
        for i in range(len(ranked)):
            g = ranked[i]['game']
            start_utc = datetime.strptime(g['startTimeUTC'].replace('Z', ''), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=pytz.utc)
            stop_utc = start_utc + timedelta(hours=2, minutes=30)
            
            p_start = start_utc - timedelta(minutes=30)
            if i > 0:
                prev_stop = datetime.strptime(ranked[i-1]['game']['startTimeUTC'].replace('Z', ''), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=pytz.utc) + timedelta(hours=2, minutes=30)
                p_start = max(p_start, prev_stop)

            if start_utc > p_start:
                xml.append(f'<programme start="{p_start.strftime("%Y%m%d%H%M%S")} +0000" stop="{start_utc.strftime("%Y%m%d%H%M%S")} +0000" channel="NHL.Live.1">')
                xml.append(f'  <title lang="fr">🏒 PREGAME : {g["awayTeam"]["abbrev"]} @ {g["homeTeam"]["abbrev"]}</title>')
                xml.append(f'  <desc lang="fr">Début à {start_utc.astimezone(tz_mtl).strftime("%H:%M")}.</desc>')
                xml.append('</programme>')

            xml.append(f'<programme start="{start_utc.strftime("%Y%m%d%H%M%S")} +0000" stop="{stop_utc.strftime("%Y%m%d%H%M%S")} +0000" channel="NHL.Live.1">')
            xml.append(f'  <title lang="fr">{"[LIVE]" if g["gameState"] in ["LIVE", "CRIT"] else "[PRE]"} {g["awayTeam"]["abbrev"]} @ {g["homeTeam"]["abbrev"]}</title>')
            xml.append(f'  <desc lang="fr">{get_custom_desc(g)}</desc>')
            xml.append('</programme>')

        # CANAUX 2 À 5 (DYNAMIQUES)
        for i in range(1, min(len(ranked), 5)):
            channel_id = f"NHL.Live.{i+1}"
            g = ranked[i]['game']
            s_utc = datetime.strptime(g['startTimeUTC'].replace('Z', ''), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=pytz.utc)
            p_start = s_utc - timedelta(minutes=30)
            m_stop = s_utc + timedelta(hours=2, minutes=30)
            
            xml.append(f'<programme start="{p_start.strftime("%Y%m%d%H%M%S")} +0000" stop="{m_stop.strftime("%Y%m%d%H%M%S")} +0000" channel="{channel_id}">')
            xml.append(f'  <title lang="fr">{g["awayTeam"]["abbrev"]} @ {g["homeTeam"]["abbrev"]}</title>')
            xml.append(f'  <desc lang="fr">{get_custom_desc(g)}</desc>')
            xml.append('</programme>')

    xml.append('</tv>')
    return Response("\n".join(xml), mimetype='text/xml')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
    
