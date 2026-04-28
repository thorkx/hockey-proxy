import requests
from flask import Flask, redirect, Response, make_response

app = Flask(__name__)

# =================================================================
# 1. CONFIGURATION (TES ACCÈS OMEGATV)
# =================================================================
USER = "tDcJnv4jMM"
PASS = "2khBtbUZuV"
BASE_DOMAIN = "omegatv.live:80"
BASE_URL = "https://thorkx-hockey-proxy.vercel.app"

# IDs des chaînes chez ton fournisseur
CH = {
    "RDS": "184813", "RDS2": "184814", "RDSInfo": "184815",
    "TVASports": "184811", "TVASports2": "184812",
    "SNEast": "71518", "SNWest": "71521", "SNPacific": "71520",
    "SN1": "71519", "SN4K": "157674", "SNOne4K": "157675"
}

def get_url(cid):
    return f"http://{BASE_DOMAIN}/{USER}/{PASS}/{cid}.ts"

# Mapping pour faire le pont avec l'API de la NHL
MAPPING = {
    "RDS": get_url(CH["RDS"]),
    "RDS2": get_url(CH["RDS2"]),
    "SN": get_url(CH["SNEast"]), # L'API envoie souvent juste 'SN' ou 'SNE'
    "SNE": get_url(CH["SNEast"]),
    "SNW": get_url(CH["SNWest"]),
    "SNP": get_url(CH["SNPacific"]),
    "SN1": get_url(CH["SN1"]),
    "TVAS": get_url(CH["TVASports"]),
    "TVAS2": get_url(CH["TVASports2"]),
    "DEFAULT": get_url(CH["RDS"])
}


# Tes priorités
ULTRA_PRIORITY = ["MTL"]
SECONDARY_FAVORITES = ["COL", "BUF", "UTA"]

# =================================================================
# 2. LE CERVEAU (RANKING DES MATCHS)
# =================================================================

def get_ranked_games():
    import requests
    from datetime import datetime, timedelta
    
    # On définit la plage de dates : d'aujourd'hui à +4 jours
    start_date = datetime.now()
    combined_games = []
    
    # On boucle sur 4 jours pour couvrir aujourd'hui et les 3 prochains
    for i in range(4):
        current_date_str = (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
        url = f"https://api-web.nhle.com/v1/schedule/{current_date_str}"
        
        try:
            r = requests.get(url, timeout=5)
            data = r.json()
            # L'API peut renvoyer plusieurs jours, on filtre celui qui nous intéresse
            for day in data.get('gameWeek', []):
                if day.get('date') == current_date_str:
                    combined_games.extend(day.get('games', []))
        except Exception as e:
            print(f"Erreur pour la date {current_date_str}: {e}")
            continue

    ranked_list = []
    seen_game_ids = set()

    for g in combined_games:
        game_id = g.get('id')
        if game_id in seen_game_ids or g.get('gameState') == "OFF":
            continue
        seen_game_ids.add(game_id)

        home, away = g['homeTeam']['abbrev'], g['awayTeam']['abbrev']
        is_mtl = (home == "MTL" or away == "MTL")
        
        # Scoring de priorité
        score = 1000 if is_mtl else 10
        if home in ULTRA_PRIORITY or away in ULTRA_PRIORITY:
            score += 100

        # Extraction et sélection du diffuseur
        tv_list = [tv['network'] for tv in g.get('tvBroadcasts', []) if tv['countryCode'] == 'CA']
        best_url = MAPPING.get("DEFAULT")
        best_bonus = -1

        for net in tv_list:
            match_key = next((k for k in MAPPING if k in net), None)
            if not match_key: continue
            
            # Ton échelle de priorité : RDS(MTL) > SN > RDS > TVAS
            bonus = 500 if (is_mtl and "RDS" in net) else (300 if "SN" in net else (100 if "RDS" in net else 50))
            if bonus > best_bonus:
                best_bonus, best_url = bonus, MAPPING[match_key]

        ranked_list.append({
            'game': g,
            'url': best_url,
            'total_score': score + best_bonus
        })

    # Tri chronologique pour que l'EPG soit dans le bon ordre
    ranked_list.sort(key=lambda x: x['game']['startTimeUTC'])
    return ranked_list
    

# =================================================================
# 3. LES ROUTES (INTERFACES POUR TIVIMATE)
# =================================================================

# LA VIDÉO
@app.route('/nhl-live', defaults={'path': ''})
@app.route('/nhl-live/<path:path>')
def redirect_to_nhl(path):
    ranked = get_ranked_games()
    final_url = ranked[0]['url'] if ranked else MAPPING["DEFAULT"]
    response = make_response(redirect(final_url, code=302))
    response.headers['User-Agent'] = 'IPTVSmarters/1.0.3'
    return response

# LA PLAYLIST (M3U)
@app.route('/playlist.m3u')
def generate_m3u():
    ranked = get_ranked_games()
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    
    m3u = ["#EXTM3U"]
    
    # On détermine quels matchs sont "actifs" (en cours ou pregame de 30 min débuté)
    active_matches = []
    for item in ranked:
        start_dt = datetime.strptime(item['game']['startTimeUTC'].replace('Z', ''), "%Y-%m-%dT%H:%M:%S")
        if item['game']['gameState'] in ["LIVE", "CRIT"] or now >= (start_dt - timedelta(minutes=30)):
            active_matches.append(item)

    # On s'assure d'avoir au moins un canal même si rien ne joue
    display_count = max(1, len(active_matches))
    
    for i in range(display_count):
        channel_num = i + 1
        if i < len(active_matches):
            g = active_matches[i]['game']
            url = active_matches[i]['url']
            label = f"({g['awayTeam']['abbrev']} @ {g['homeTeam']['abbrev']})"
        else:
            url = MAPPING.get("DEFAULT")
            label = "(En attente)"
            
        m3u.append(f'#EXTINF:-1 tvg-id="NHL.Live.{channel_num}" tvg-name="NHL LIVE {channel_num}" group-title="Hockey", NHL LIVE {channel_num} {label}')
        m3u.append(url)
    
    return Response("\n".join(m3u), mimetype='text/plain')
    
# LE GUIDE (EPG)
@app.route('/epg.xml')
def generate_epg():
    ranked = get_ranked_games()
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<tv>']
    
    # Déclaration des 5 canaux
    for i in range(1, 6):
        xml.append(f'<channel id="NHL.Live.{i}"><display-name>NHL LIVE {i}</display-name></channel>')
    
    from datetime import datetime, timedelta
    import pytz
    
    # On utilise UTC pour la logique interne
    now_utc = datetime.utcnow().replace(tzinfo=pytz.utc)
    tz_mtl = pytz.timezone('America/Montreal')

    if ranked:
        # --- CANAL 1 (MASTER) ---
        for i in range(len(ranked)):
            item = ranked[i]
            g = item['game']
            
            # Conversion du début du match
            start_utc = datetime.strptime(g['startTimeUTC'].replace('Z', ''), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=pytz.utc)
            
            # DURÉE CHANGÉE À 2H30
            stop_utc = start_utc + timedelta(hours=2, minutes=30)
            
            # Formatage pour le XML
            start_fmt = start_utc.strftime("%Y%m%d%H%M%S") + " +0000"
            stop_fmt = stop_utc.strftime("%Y%m%d%H%M%S") + " +0000"

            # 1. Logique du Pregame (30 min max)
            pregame_start = start_utc - timedelta(minutes=30)
            actual_pregame_start = pregame_start
            
            # Si un match précédait celui-ci, on ne commence le pregame qu'après la fin du précédent
            if i > 0:
                prev_start = datetime.strptime(ranked[i-1]['game']['startTimeUTC'].replace('Z', ''), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=pytz.utc)
                prev_stop = prev_start + timedelta(hours=2, minutes=30)
                if prev_stop > pregame_start:
                    actual_pregame_start = prev_stop

            # Insertion du bloc Pregame si l'espace existe
            if start_utc > actual_pregame_start:
                p_start_fmt = actual_pregame_start.strftime("%Y%m%d%H%M%S") + " +0000"
                xml.append(f'<programme start="{p_start_fmt}" stop="{start_fmt}" channel="NHL.Live.1">')
                xml.append(f'  <title lang="fr">🏒 PREGAME : {g["awayTeam"]["abbrev"]} @ {g["homeTeam"]["abbrev"]}</title>')
                xml.append(f'  <desc lang="fr">Préparation et analyses avant le début à {start_utc.astimezone(tz_mtl).strftime("%H:%M")}.</desc>')
                xml.append('</programme>')

            # 2. Insertion du Match
            status = "[LIVE]" if g['gameState'] in ["LIVE", "CRIT"] else "[PRE]"
            xml.append(f'<programme start="{start_fmt}" stop="{stop_fmt}" channel="NHL.Live.1">')
            xml.append(f'  <title lang="fr">{status} {g["awayTeam"]["abbrev"]} @ {g["homeTeam"]["abbrev"]}</title>')
            xml.append(f'  <desc lang="fr">{get_custom_desc(g)}</desc>')
            xml.append('</programme>')

        # --- CANAUX 2 À 5 (DYNAMIQUES) ---
        for i in range(1, min(len(ranked), 5)):
            channel_id = f"NHL.Live.{i+1}"
            g = ranked[i]['game']
            s_utc = datetime.strptime(g['startTimeUTC'].replace('Z', ''), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=pytz.utc)
            # Match + Pregame simple de 30min pour les canaux secondaires
            p_start = (s_utc - timedelta(minutes=30)).strftime("%Y%m%d%H%M%S") + " +0000"
            m_stop = (s_utc + timedelta(hours=2, minutes=30)).strftime("%Y%m%d%H%M%S") + " +0000"
            
            xml.append(f'<programme start="{p_start}" stop="{m_stop}" channel="{channel_id}">')
            xml.append(f'  <title lang="fr">{g["awayTeam"]["abbrev"]} @ {g["homeTeam"]["abbrev"]}</title>')
            xml.append(f'  <desc lang="fr">Match en direct sur le flux secondaire {i+1}.</desc>')
            xml.append('</programme>')

    xml.append('</tv>')
    return Response("\n".join(xml), mimetype='text/xml')
    


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
    
