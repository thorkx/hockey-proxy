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
    try:
        url = "https://api-web.nhle.com/v1/score/now"
        data = requests.get(url, timeout=5).json()
        results = []
        for game in data.get('games', []):
            state = game.get('gameState')
            if state not in ["PRE", "LIVE", "CRIT"]: continue

            away = game['awayTeam']['abbrev']
            home = game['homeTeam']['abbrev']
            is_mtl = (away in ULTRA_PRIORITY or home in ULTRA_PRIORITY)
            
            # Score de base (Équipe + État du match + Période)
            score = 0
            if is_mtl: score += 1000
            elif away in SECONDARY_FAVORITES or home in SECONDARY_FAVORITES: score += 100
            
            if state == "CRIT": score += 800
            elif state == "LIVE": score += 50
            period = game.get('periodDescriptor', {}).get('number', 1)
            score += (period * 20)

            # Choix du meilleur diffuseur selon tes nouvelles priorités
            tv_list = [tv['network'] for tv in game.get('tvBroadcasts', []) if tv['countryCode'] == 'CA']
            best_tv_url, best_tv_bonus = None, -1

            for net in tv_list:
                if net not in MAPPING: continue
                bonus = 0
                
                # 1. Priorité Absolue : RDS pour les Canadiens
                if is_mtl and "RDS" in net:
                    bonus = 500
                
                # 2. Priorité secondaire : Sportsnet pour tout le reste
                elif "SN" in net:
                    bonus = 100
                
                # 3. Dernier choix : TVA Sports
                elif "TVAS" in net:
                    bonus = 10
                
                # 4. RDS pour un match non-MTL (si SN n'est pas dispo)
                elif "RDS" in net:
                    bonus = 50

                if bonus > best_tv_bonus:
                    best_tv_bonus = bonus
                    best_tv_url = MAPPING[net]
                    

            if best_tv_url:
                results.append({'game': game, 'url': best_tv_url, 'total_score': score + best_tv_bonus})
        return sorted(results, key=lambda x: x['total_score'], reverse=True)
    except:
        return []

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
    
    # Déclaration du canal (doit matcher tvg-id dans le M3U)
    xml.append('<channel id="NHL.Live">')
    xml.append('  <display-name>NHL LIVE</display-name>')
    xml.append('</channel>')
    
    if ranked:
        game_data = ranked[0]
        g = game_data['game']
        
        # 1. Nettoyage de la date (Format XMLTV : YYYYMMDDHHMMSS)
        # On retire les tirets, les deux-points, le 'T' et le 'Z'
        raw_start = g['startTimeUTC'].replace('-', '').replace(':', '').replace('T', '').replace('Z', '')
        
        # Sécurité : l'API peut parfois omettre les secondes
        if len(raw_start) == 12:
            raw_start += "00"
            
        start_xmltv = f"{raw_start} +0000"
        
        # 2. Calcul d'une heure de fin (stop) à +4 heures (approximation sécuritaire)
        try:
            from datetime import datetime, timedelta
            start_dt = datetime.strptime(raw_start, "%Y%m%d%H%M%S")
            stop_dt = start_dt + timedelta(hours=4)
            stop_xmltv = stop_dt.strftime("%Y%m%d%H%M%S") + " +0000"
        except:
            # Repli si la conversion échoue
            stop_xmltv = f"{raw_start[:8]}235959 +0000"

        # 3. Construction du bloc programme
        prefix = "[P1]" if (g['awayTeam']['abbrev'] in ULTRA_PRIORITY or g['homeTeam']['abbrev'] in ULTRA_PRIORITY) else "[LIVE]"
        
        next_info = ""
        if len(ranked) > 1:
            n = ranked[1]['game']
            next_info = f"\nSuivant : {n['awayTeam']['abbrev']} @ {n['homeTeam']['abbrev']}"

        xml.append(f'<programme start="{start_xmltv}" stop="{stop_xmltv}" channel="NHL.Live">')
        xml.append(f'  <title lang="fr">{prefix} {g["awayTeam"]["abbrev"]} vs {g["homeTeam"]["abbrev"]}</title>')
        xml.append(f'  <desc lang="fr">Match en direct (Priorité NHL).{next_info}</desc>')
        xml.append('</programme>')
    
    xml.append('</tv>')
    
    # On retourne le XML avec le bon type MIME pour le lecteur
    return Response("\n".join(xml), mimetype='text/xml')
    

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
    
