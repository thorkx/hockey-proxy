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
    from datetime import datetime

    # URL de l'API NHL (Scoreboard)
    NHL_API_URL = "https://api-web.nhle.com/v1/score/now"
    
    try:
        response = requests.get(NHL_API_URL)
        data = response.json()
    except Exception as e:
        print(f"Erreur API: {e}")
        return []

    ranked_list = []
    
    # On récupère tous les matchs
    all_games = data.get('games', [])
    
    for g in all_games:
        # ÉTAPE 1: Filtrer les états. On garde LIVE, CRIT (moment clé) et PRE (à venir)
        state = g.get('gameState')
        if state not in ["LIVE", "CRIT", "PRE"]:
            continue

        home = g['homeTeam']['abbrev']
        away = g['awayTeam']['abbrev']
        is_mtl = (home == "MTL" or away == "MTL")
        
        # ÉTAPE 2: Calcul du score de priorité du match
        base_score = 0
        if is_mtl:
            base_score = 1000  
        elif home in ULTRA_PRIORITY or away in ULTRA_PRIORITY:
            base_score = 100   
        else:
            base_score = 10    

        # ÉTAPE 3: Trouver le meilleur diffuseur
        tv_list = [tv['network'] for tv in g.get('tvBroadcasts', []) if tv['countryCode'] == 'CA']
        
        best_tv_url = None
        best_tv_bonus = -1

        for net in tv_list:
            # On cherche si le réseau est dans notre MAPPING
            match_key = None
            for key in MAPPING.keys():
                if key in net: # Capture "SNE", "SNW", etc.
                    match_key = key
                    break
            
            if not match_key:
                continue

            bonus = 0
            if is_mtl and "RDS" in net:
                bonus = 500
            elif "SN" in net:
                bonus = 300
            elif "RDS" in net: # RDS pour match non-MTL
                bonus = 100
            elif "TVAS" in net:
                bonus = 50

            if bonus > best_tv_bonus:
                best_tv_bonus = bonus
                best_tv_url = MAPPING[match_key]

        # ÉTAPE 4: AJOUT À LA LISTE (C'est ici que ça se joue)
        # Si on a trouvé une URL, on ajoute le match à notre collection
        if best_tv_url:
            ranked_list.append({
                'game': g,
                'url': best_tv_url,
                'total_score': base_score + best_tv_bonus
            })

    # ÉTAPE 5: TRI COMPLET
    # On trie par score (priorité), puis par heure pour les matchs futurs
    ranked_list.sort(key=lambda x: (x['total_score'], x['game']['startTimeUTC']), reverse=True)

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

    for i in range(len(ranked)):
        item = ranked[i]
        g = item['game']
        
        # 1. Infos du match actuel
        raw_start = g['startTimeUTC'].replace('-', '').replace(':', '').replace('T', '').replace('Z', '')
        if len(raw_start) == 12: raw_start += "00"
        
        start_dt = datetime.strptime(raw_start, "%Y%m%d%H%M%S")
        # On estime la fin du match à +3h
        stop_dt = start_dt + timedelta(hours=3)
        
        start_xmltv = start_dt.strftime("%Y%m%d%H%M%S") + " +0000"
        stop_xmltv = stop_dt.strftime("%Y%m%d%H%M%S") + " +0000"

        status = "[LIVE]" if g['gameState'] in ["LIVE", "CRIT"] else "[PRE]"
        title = f"{status} {g['awayTeam']['abbrev']} @ {g['homeTeam']['abbrev']}"
        desc = f"Diffusion sur {item['url'].split('/')[-1]}."

        xml.append(f'<programme start="{start_xmltv}" stop="{stop_xmltv}" channel="NHL.Live">')
        xml.append(f'  <title lang="fr">{title}</title>')
        xml.append(f'  <desc lang="fr">{desc}</desc>')
        xml.append('</programme>')

        # 2. Logique "Prochain Match" (Filler)
        # S'il y a un match après celui-ci, on remplit l'espace vide
        if i + 1 < len(ranked):
            next_g = ranked[i+1]['game']
            next_start_raw = next_g['startTimeUTC'].replace('-', '').replace(':', '').replace('T', '').replace('Z', '')
            if len(next_start_raw) == 12: next_start_raw += "00"
            next_start_dt = datetime.strptime(next_start_raw, "%Y%m%d%H%M%S")

            # Si l'espace entre la fin du match actuel et le prochain est > 1 minute
            if next_start_dt > stop_dt:
                filler_start = stop_xmltv
                filler_stop = next_start_dt.strftime("%Y%m%d%H%M%S") + " +0000"
                
                xml.append(f'<programme start="{filler_start}" stop="{filler_stop}" channel="NHL.Live">')
                xml.append(f'  <title lang="fr">➡️ PROCHAINEMENT : {next_g["awayTeam"]["abbrev"]} @ {next_g["homeTeam"]["abbrev"]}</title>')
                xml.append(f'  <desc lang="fr">Le stream basculera automatiquement au début du match.</desc>')
                xml.append('</programme>')
    
    xml.append('</tv>')
    return Response("\n".join(xml), mimetype='text/xml')
    
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
    
