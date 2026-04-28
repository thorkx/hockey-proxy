import requests
from flask import Flask, redirect, Response, make_response

app = Flask(__name__)

# --- CONFIGURATION DU FOURNISSEUR (OMEGATV) ---
USER = "tDcJnv4jMM"
PASS = "2khBtbUZuV"
BASE_DOMAIN = "omegatv.live:80"

# --- IDs DES CHAÎNES ---
CH = {
    "RDS": "184813",
    "RDS2": "184814",
    "RDSInfo": "184815",
    "TVASports": "184811",
    "TVASports2": "184812",
    "SNEast": "71518",
    "SNWest": "71521",
    "SNPacific": "71520",
    "SN1": "71519",
    "SN4K": "157674",
    "SNOne4K": "157675"
}

def get_url(cid):
    return f"http://{BASE_DOMAIN}/{USER}/{PASS}/{cid}.ts"

# --- MAPPING API NHL -> NOS URLs ---
MAPPING = {
    "RDS": get_url(CH["RDS"]),
    "RDS2": get_url(CH["RDS2"]),
    "SNE": get_url(CH["SNEast"]),
    "SNW": get_url(CH["SNWest"]),
    "SNP": get_url(CH["SNPacific"]),
    "SN1": get_url(CH["SN1"]),
    "TVAS": get_url(CH["TVASports"]),
    "TVAS2": get_url(CH["TVASports2"]),
    "DEFAULT": get_url(CH["RDS"])
}

# --- CONFIGURATION DES PRIORITÉS ---
ULTRA_PRIORITY = ["MTL"]
SECONDARY_FAVORITES = ["COL", "BUF", "UTA"]
BASE_URL = "https://hockey-proxy.vercel.app"

def get_ranked_games():
    """Fonction utilitaire pour calculer le score de tous les matchs actifs."""
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
            
            # 1. Score de base du match
            game_score = 0
            if is_mtl: game_score += 1000
            elif away in SECONDARY_FAVORITES or home in SECONDARY_FAVORITES: game_score += 100
            
            if state == "CRIT": game_score += 800
            elif state == "LIVE": game_score += 50
            period = game.get('periodDescriptor', {}).get('number', 1)
            game_score += (period * 20)

            # 2. Choix du meilleur diffuseur selon tes règles
            tv_list = [tv['network'] for tv in game.get('tvBroadcasts', []) if tv['countryCode'] == 'CA']
            best_tv_url = None
            best_tv_bonus = -1

            for net in tv_list:
                if net not in MAPPING: continue
                
                bonus = 0
                if is_mtl and "RDS" in net: bonus = 100
                elif not is_mtl and "SN" in net: bonus = 50
                elif "TVAS" in net: bonus = 10
                
                if bonus > best_tv_bonus:
                    best_tv_bonus = bonus
                    best_tv_url = MAPPING[net]

            if best_tv_url:
                results.append({
                    'game': game,
                    'url': best_tv_url,
                    'total_score': game_score + best_tv_bonus
                })

        return sorted(results, key=lambda x: x['total_score'], reverse=True)
    except:
        return []

@app.route('/nhl-live', defaults={'path': ''})
@app.route('/nhl-live/<path:path>')
def redirect_to_nhl(path):
    ranked = get_ranked_games()
    final_url = ranked[0]['url'] if ranked else MAPPING["DEFAULT"]
    response = make_response(redirect(final_url, code=302))
    response.headers['User-Agent'] = 'IPTVSmarters/1.0.3'
    return response

@app.route('/playlist.m3u')
def generate_m3u():
    ranked = get_ranked_games()
    channel_name = "🏒 NHL LIVE DYNAMIQUE"
    
    if ranked:
        best = ranked[0]['game']
        away = best['awayTeam']['abbrev']
        home = best['homeTeam']['abbrev']
        if best['gameState'] in ["LIVE", "CRIT"]:
            a_s = best['awayTeam'].get('score', 0)
            h_s = best['homeTeam'].get('score', 0)
            p = best.get('periodDescriptor', {}).get('number', 1)
            channel_name = f"🏒 {away} ({a_s}) @ {home} ({h_s}) - P{p}"
        else:
            channel_name = f"🏒 PRE: {away} @ {home}"

    m3u = f"#EXTM3U\n#EXTINF:-1 tvg-id=\"NHL.Live\" tvg-name=\"NHL LIVE\" group-title=\"SPORTS\",{channel_name}\n{BASE_URL}/nhl-live/.ts"
    return Response(m3u, mimetype='text/plain')

@app.route('/epg.xml')
def generate_epg():
    ranked = get_ranked_games()
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<tv>']
    xml.append('<channel id="NHL.Live"><display-name>NHL LIVE</display-name></channel>')

    if ranked:
        best = ranked[0]['game']
        away = best['awayTeam']['abbrev']
        home = best['homeTeam']['abbrev']
        
        prefix = "[P1]" if (away in ULTRA_PRIORITY or home in ULTRA_PRIORITY) else "[LIVE]"
        next_info = f"\nÀ SUIVRE : {ranked[1]['game']['awayTeam']['abbrev']} @ {ranked[1]['game']['homeTeam']['abbrev']}" if len(ranked) > 1 else ""
        
        start = best['startTimeUTC'].replace('-', '').replace(':', '').replace('Z', ' +0000')
        xml.append(f'<programme start="{start}" channel="NHL.Live">')
        xml.append(f'  <title lang="fr">{prefix} {away} vs {home}</title>')
        xml.append(f'  <desc lang="fr">Match sélectionné selon tes priorités.{next_info}</desc>')
        xml.append('</programme>')

    xml.append('</tv>')
    return Response("\n".join(xml), mimetype='text/xml')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
    
