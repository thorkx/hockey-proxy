from flask import Flask, redirect, Response
import requests

app = Flask(__name__)

# ==========================================
# TA CONFIGURATION (À PERSONNALISER)
# ==========================================
# Remplace les URLs ci-dessous par tes liens IPTV réels (ceux que tu as trouvés)
MAPPING = {
    "RDS": "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV/184813",
    "TVAS": "http://ton-serveur.com:8080/live/user/pass/ID_TVAS.ts",
    "SN": "http://ton-serveur.com:8080/live/user/pass/ID_SN.ts",
    "SNE": "http://ton-serveur.com:8080/live/user/pass/ID_SN_EAST.ts",
    "CBC": "http://ton-serveur.com:8080/live/user/pass/ID_CBC.ts",
    "DEFAULT": "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV/184813" # Ton RDS par défaut
}

FAVORITES = ["MTL", "COL", "PHI", "PIT", "TOR", "UTA"]
BASE_URL = "https://thorkx-hockey-proxy.vercel.app"

@app.route('/')
def home():
    return "NHL Proxy is running. Use /playlist.m3u"

@app.route('/playlist.m3u')
def generate_m3u():
    # On ajoute /.ts à la fin pour "tromper" les lecteurs capricieux
    m3u_content = f"""#EXTM3U
#EXTINF:-1 tvg-id="NHL.Live" tvg-name="NHL LIVE" group-title="SPORTS PERSO",🏒 NHL LIVE DYNAMIQUE
{BASE_URL}/nhl-live/.ts
"""
    return Response(m3u_content, mimetype='text/plain')

# On utilise <path:path> pour accepter n'importe quoi après /nhl-live/ (comme le /.ts)
@app.route('/nhl-live/', defaults={'path': ''})
@app.route('/nhl-live/<path:path>')
def redirect_to_nhl(path):
    try:
        url = "https://api-web.nhle.com/v1/score/now"
        data = requests.get(url, timeout=5).json()
        
        target_stream = None
        for game in data.get('games', []):
            if game['awayTeam']['abbrev'] in FAVORITES or game['homeTeam']['abbrev'] in FAVORITES:
                if game.get('gameState') in ["PRE", "LIVE", "CRIT"]:
                    ca_tv = [tv['network'] for tv in game.get('tvBroadcasts', []) if tv['countryCode'] == 'CA']
                    for network in ca_tv:
                        if network in MAPPING:
                            target_stream = MAPPING[network]
                            break
                if target_stream: break

        final_url = target_stream or MAPPING["DEFAULT"]
        
        # Création de la réponse de redirection
        response = make_response(redirect(final_url, code=302))
        
        # Headers pour forcer le mode vidéo et non téléchargement
        response.headers['Content-Type'] = 'video/mp2t'
        response.headers['User-Agent'] = 'IPTVSmarters/1.0.3'
        
        return response

    except Exception:
        return redirect(MAPPING["DEFAULT"], code=302)
