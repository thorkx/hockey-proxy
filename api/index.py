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


# Priorités Hockey
ULTRA_NHL = ["MTL"]
FAV_NHL = ["COL", "BUF", "UTA", "EDM"]

# Priorités Basket
ULTRA_NBA = ["TOR"] # Les Raptors par exemple
FAV_NBA = ["LAL", "GSW", "BOS"]

CH = {
    "RDS": "184813", "RDS2": "184814", "RDSInfo": "184815",
    "TVASports": "184811", "TVASports2": "184812",
    "SNEast": "71518", "SNWest": "71521", "SNPacific": "71520",
    "SN1": "71519", "SN4K": "157674", "SNOne4K": "157675",
    "TSN1": "71501", "TSN2": "71502" # Ajout de TSN pour la NBA souvent
}

def get_url(cid):
    return f"http://{BASE_DOMAIN}/{USER}/{PASS}/{cid}.ts"

MAPPING = {
    "RDS": get_url(CH["RDS"]), "RDS2": get_url(CH["RDS2"]),
    "SN": get_url(CH["SNEast"]), "SNE": get_url(CH["SNEast"]),
    "SNW": get_url(CH["SNWest"]), "SNP": get_url(CH["SNPacific"]),
    "SN1": get_url(CH["SN1"]), "TVAS": get_url(CH["TVASports"]),
    "TVAS2": get_url(CH["TVASports2"]),
    "TSN": get_url(CH["TSN1"]),
    "DEFAULT": get_url(CH["RDS"])
}

# =================================================================
# 2. LOGIQUE DE PLACEMENT ET RANKING
# =================================================================

def assign_channels(ranked_games):
    channels_data = {i: [] for i in range(1, 6)}
    occupation_slots = {i: [] for i in range(1, 6)}
    
    for item in ranked_games:
        start_utc = item['start_dt']
        # Basket et Hockey : on réserve 3h15
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

def get_custom_desc(item):
    """Génère la description avec le logo unique du sport"""
    g = item['game']
    sport_logo = "🏒" if item['sport'] == 'NHL' else "🏀"
    
    # Déterminer si c'est un favori pour le texte
    is_priority = item['score'] >= 800
    priority_text = " - Prioritaire" if is_priority else ""
    
    return f"{sport_logo} Diffusion {item['sport']}{priority_text}"

def get_ranked_games():
    now = datetime.now()
    all_raw_games = []
    
    # --- FETCH NHL ---
    for i in range(3):
        date_str = (now + timedelta(days=i)).strftime("%Y-%m-%d")
        try:
            r = requests.get(f"https://api-web.nhle.com/v1/schedule/{date_str}", timeout=5).json()
            for day in r.get('gameWeek', []):
                if day['date'] == date_str:
                    for g in day.get('games', []):
                        if g.get('gameState') == "OFF": continue
                        if "12:00:00" in g['startTimeUTC'] and g.get('gameState') != "LIVE": continue
                        
                        h, a = g['homeTeam']['abbrev'], g['awayTeam']['abbrev']
                        score = 2000 if (h in ULTRA_NHL or a in ULTRA_NHL) else (1000 if (h in FAV_NHL or a in FAV_NHL) else 10)
                        
                        all_raw_games.append({
                            'sport': 'NHL',
                            'title': f"{a} @ {h}",
                            'game': g, # Gardé pour la compatibilité
                            'start_dt': datetime.strptime(g['startTimeUTC'].replace('Z', ''), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=pytz.utc),
                            'score': score,
                            'networks': [t['network'] for t in g.get('tvBroadcasts', []) if t['countryCode'] == 'CA'],
                            'id': f"nhl_{g['id']}"
                        })
        except: continue        
    # --- FETCH NBA (Version Scoreboard V2 - Blindée) ---
    try:
        # On utilise une date formatée pour l'API
        date_nba = now.strftime("%m/%d/%Y")
        nba_url = f"https://stats.nba.com/stats/scoreboardv2?DayOffset=0&LeagueID=00&gameDate={date_nba}"
        
        # SANS CES HEADERS, LA NBA BLOQUE LA REQUÊTE
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.nba.com/",
            "Origin": "https://www.nba.com"
        }

        r = requests.get(nba_url, headers=headers, timeout=5)
        if r.status_code == 200:
            data = r.json()
            # Dans ScoreboardV2, les matchs sont dans resultSets[0]
            games_list = data['resultSets'][0]['rowSet']
            headers_list = data['resultSets'][0]['headers']
            
            # On map les index pour être sûr de prendre les bonnes colonnes
            idx_id = headers_list.index("GAME_ID")
            idx_home = headers_list.index("HOME_TEAM_ID") # On utilisera une map pour les codes si besoin
            idx_status = headers_list.index("GAME_STATUS_TEXT")
            idx_date = headers_list.index("GAME_DATE_EST")
            
            # Pour V2, on a souvent besoin des abréviations qui sont dans le resultSet 1 ou 5
            # Mais plus simple : on va utiliser le "GAMECODE" qui contient "20260428/BOSPHI"
            idx_code = headers_list.index("GAMECODE")

            for g in games_list:
                game_code = g[idx_code] # Ex: "20260428/BOSPHI"
                teams = game_code.split('/')[1]
                away_code = teams[:3]
                home_code = teams[3:]
                
                score = 5
                if home_code in ULTRA_NBA or away_code in ULTRA_NBA: score = 1500
                elif home_code in FAV_NBA or away_code in FAV_NBA: score = 800
                
                # Heure : ScoreboardV2 est en EST. On convertit pour notre logique UTC
                # La NBA commence souvent ses matchs à 19:00 EST (00:00 UTC)
                # Pour faire simple ici, on simule l'heure, mais l'API donne le status
                dt = now.replace(hour=20, minute=0, second=0, microsecond=0).replace(tzinfo=pytz.utc)

                all_raw_games.append({
                    'sport': 'NBA',
                    'title': f"{away_code} @ {home_code}",
                    'game': g,
                    'start_dt': dt,
                    'score': score,
                    'networks': [], 
                    'id': f"nba_{g[idx_id]}"
                })
    except Exception as e:
        print(f"Erreur NBA V2: {e}")
        
    
    # --- RANKING ---
    ranked = []
    for item in all_raw_games:
        # Logique de sélection d'URL (identique)
        best_url, best_bonus = MAPPING["DEFAULT"], -1
        for net in item['networks']:
            k = next((key for key in MAPPING if key in net), None)
            if not k: continue
            bonus = 500 if (item['sport'] == 'NHL' and "RDS" in net) else 200
            if bonus > best_bonus: best_bonus, best_url = bonus, MAPPING[k]
        
        item['url'] = best_url
        item['total_score'] = item['score'] + best_bonus
        item['desc'] = get_custom_desc(item) # On génère la desc ici
        ranked.append(item)

    ranked.sort(key=lambda x: (-x['total_score'], x['start_dt']))
    return ranked

# =================================================================
# 3. ROUTES FLASK
# =================================================================

@app.route('/nhl-live/<int:ch_num>')
def redirect_channel(ch_num):
    ranked = get_ranked_games()
    grid = assign_channels(ranked)
    now = datetime.utcnow().replace(tzinfo=pytz.utc)
    match = next((i for i in grid.get(ch_num, []) if i['start_dt'] - timedelta(minutes=30) <= now <= i['start_dt'] + timedelta(hours=3, minutes=30)), None)
    url = match['url'] if match else MAPPING["DEFAULT"]
    res = make_response(redirect(url, code=302))
    res.headers['User-Agent'] = 'IPTVSmarters/1.0.3'
    return res

@app.route('/playlist.m3u')
def generate_m3u():
    ranked = get_ranked_games()
    grid = assign_channels(ranked)
    m3u = ["#EXTM3U"]
    for i in range(1, 6):
        now = datetime.utcnow().replace(tzinfo=pytz.utc)
        current = next((item for item in grid[i] if now <= item['start_dt'] + timedelta(hours=3)), None)
        label = f"({current['title']})" if current else "(En attente)"
        m3u.append(f'#EXTINF:-1 tvg-id="NHL.Live.{i}" tvg-name="NHL LIVE {i}" group-title="Sports Multi", NHL LIVE {i} {label}')
        m3u.append(f"http://{request.host}/nhl-live/{i}")
    return Response("\n".join(m3u), mimetype='text/plain')
@app.route('/epg.xml')
def generate_epg():
    ranked = get_ranked_games()
    grid = assign_channels(ranked)
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<tv>']
    for i in range(1, 6): xml.append(f'<channel id="NHL.Live.{i}"><display-name>LIVE {i}</display-name></channel>')
    
    tz_mtl = pytz.timezone('America/Montreal')
    for ch_num, matches in grid.items():
        for item in matches:
            s_utc = item['start_dt']
            sport_logo = "🏒" if item['sport'] == 'NHL' else "🏀"
            
            # Pregame avec logo unique
            xml.append(f'<programme start="{(s_utc-timedelta(minutes=30)).strftime("%Y%m%d%H%M%S")} +0000" stop="{s_utc.strftime("%Y%m%d%H%M%S")} +0000" channel="NHL.Live.{ch_num}">')
            xml.append(f'  <title lang="fr">{sport_logo} PREGAME : {item["title"]}</title>')
            xml.append(f'  <desc lang="fr">Début à {s_utc.astimezone(tz_mtl).strftime("%H:%M")}.</desc>')
            xml.append('</programme>')
            
            # Match
            xml.append(f'<programme start="{s_utc.strftime("%Y%m%d%H%M%S")} +0000" stop="{(s_utc+timedelta(hours=2, minutes=30)).strftime("%Y%m%d%H%M%S")} +0000" channel="NHL.Live.{ch_num}">')
            xml.append(f'  <title lang="fr">{item["title"]}</title>')
            xml.append(f'  <desc lang="fr">{item["desc"]}</desc>')
            xml.append('</programme>')
    xml.append('</tv>')
    return Response("\n".join(xml), mimetype='text/xml')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
    
