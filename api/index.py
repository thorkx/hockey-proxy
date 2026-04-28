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
    name = "🏒 NHL LIVE"
    if ranked:
        g = ranked[0]['game']
        if g['gameState'] in ["LIVE", "CRIT"]:
            name = f"🏒 {g['awayTeam']['abbrev']} ({g['awayTeam'].get('score',0)}) @ {g['homeTeam']['abbrev']} ({g['homeTeam'].get('score',0)}) - P{g.get('periodDescriptor',{}).get('number',1)}"
        else:
            name = f"🏒 PRE: {g['awayTeam']['abbrev']} @ {g['homeTeam']['abbrev']}"
    
    content = f"#EXTM3U\n#EXTINF:-1 tvg-id=\"NHL.Live\" tvg-name=\"NHL LIVE\" group-title=\"SPORTS\",{name}\n{BASE_URL}/nhl-live/.ts"
    return Response(content, mimetype='text/plain')

# LE GUIDE (EPG)
@app.route('/epg.xml')
def generate_epg():
    ranked = get_ranked_games()
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<tv>']
    xml.append('<channel id="NHL.Live"><display-name>NHL LIVE</display-name></channel>')
    
    from datetime import datetime, timedelta
    import pytz # Assure-toi que pytz est dans ton requirements.txt

    # Configuration du fuseau horaire
    tz_mtl = pytz.timezone('America/Montreal')
    now_utc = datetime.now(pytz.utc)
    now_mtl = now_utc.astimezone(tz_mtl)

    if ranked:
        # 1. Remplissage AVANT le premier match
        first_g = ranked[0]['game']
        first_start_utc = datetime.strptime(first_g['startTimeUTC'].replace('Z', ''), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=pytz.utc)
        
        if first_start_utc > now_utc + timedelta(minutes=1):
            f_start = now_utc.strftime("%Y%m%d%H%M%S") + " +0000"
            f_stop = first_start_utc.strftime("%Y%m%d%H%M%S") + " +0000"
            
            # Heure locale pour la description
            local_time = first_start_utc.astimezone(tz_mtl).strftime("%H:%M")
            
            xml.append(f'<programme start="{f_start}" stop="{f_stop}" channel="NHL.Live">')
            xml.append(f'  <title lang="fr">➡️ PROCHAINEMENT : {first_g["awayTeam"]["abbrev"]} @ {first_g["homeTeam"]["abbrev"]}</title>')
            xml.append(f'  <desc lang="fr">Début du match à {local_time} (Heure de Montréal).</desc>')
            xml.append('</programme>')

        for i in range(len(ranked)):
            item = ranked[i]
            g = item['game']
            start_utc = datetime.strptime(g['startTimeUTC'].replace('Z', ''), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=pytz.utc)
            stop_utc = start_utc + timedelta(hours=3)
            
            # Format XMLTV (Toujours envoyer en UTC avec +0000, le lecteur IPTV fera la conversion locale)
            start_fmt = start_utc.strftime("%Y%m%d%H%M%S") + " +0000"
            stop_fmt = stop_utc.strftime("%Y%m%d%H%M%S") + " +0000"

            # Logique de description dynamique
            home, away = g['homeTeam']['abbrev'], g['awayTeam']['abbrev']
            is_mtl = (home == "MTL" or away == "MTL")
            is_ultra = (home in ULTRA_PRIORITY or away in ULTRA_PRIORITY)
            
            if is_mtl:
                desc_text = f"Diffusion prioritaire NHL pour MONTRÉAL"
            elif is_ultra:
                equipe = home if home in ULTRA_PRIORITY else away
                desc_text = f"Diffusion prioritaire NHL pour {equipe}"
            else:
                desc_text = "Diffusion NHL"

            status = "[LIVE]" if g['gameState'] in ["LIVE", "CRIT"] else "[PRE]"
            xml.append(f'<programme start="{start_fmt}" stop="{stop_fmt}" channel="NHL.Live">')
            xml.append(f'  <title lang="fr">{status} {away} @ {home}</title>')
            xml.append(f'  <desc lang="fr">{desc_text}</desc>')
            xml.append('</programme>')

            # 2. Remplissage ENTRE les matchs
            if i + 1 < len(ranked):
                next_start_utc = datetime.strptime(ranked[i+1]['game']['startTimeUTC'].replace('Z', ''), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=pytz.utc)
                if next_start_utc > stop_utc:
                    f_start = stop_fmt
                    f_stop = next_start_utc.strftime("%Y%m%d%H%M%S") + " +0000"
                    next_time = next_start_utc.astimezone(tz_mtl).strftime("%H:%M")
                    
                    xml.append(f'<programme start="{f_start}" stop="{f_stop}" channel="NHL.Live">')
                    xml.append(f'  <title lang="fr">➡️ PROCHAINEMENT : {ranked[i+1]["game"]["awayTeam"]["abbrev"]} @ {ranked[i+1]["game"]["homeTeam"]["abbrev"]}</title>')
                    xml.append(f'  <desc lang="fr">Le stream basculera à {next_time}.</desc>')
                    xml.append('</programme>')

    xml.append('</tv>')
    return Response("\n".join(xml), mimetype='text/xml')
    

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
    
