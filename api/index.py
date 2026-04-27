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
    "DEFAULT": "http://ton-serveur.com:8080/live/user/pass/ID_RDS.ts" # Ton RDS par défaut
}

FAVORITES = ["MTL", "COL", "PHI", "PIT", "TOR", "UTA"]
BASE_URL = "https://hockey-proxy.vercel.app"

@app.route('/')
def home():
    return "NHL Proxy is running. Use /playlist.m3u in your IPTV player."

# --- ROUTE 1 : Génération de la Playlist ---
@app.route('/playlist.m3u')
def generate_m3u():
    m3u_content = f"""#EXTM3U
#EXTINF:-1 tvg-id="NHL.Live" tvg-name="NHL LIVE" group-title="SPORTS PERSO",🏒 NHL LIVE DYNAMIQUE
{BASE_URL}/nhl-live
"""
    return Response(m3u_content, mimetype='text/plain')

# --- ROUTE 2 : Logique de Redirection ---
@app.route('/nhl-live')
def redirect_to_nhl():
    try:
        # 1. On interroge l'API de la NHL
        url = "https://api-web.nhle.com/v1/score/now"
        response = requests.get(url, timeout=5)
        data = response.json()
        
        target_stream = None

        # 2. On cherche un match prioritaire (Favoris + Live)
        for game in data.get('games', []):
            away = game['awayTeam']['abbrev']
            home = game['homeTeam']['abbrev']
            state = game.get('gameState') # PRE, LIVE, CRIT
            
            if (home in FAVORITES or away in FAVORITES) and state in ["PRE", "LIVE", "CRIT"]:
                tv_list = game.get('tvBroadcasts', [])
                ca_tv = [tv['network'] for tv in tv_list if tv['countryCode'] == 'CA']
                
                if ca_tv:
                    # On prend le premier diffuseur matché dans notre MAPPING
                    for network in ca_tv:
                        if network in MAPPING:
                            target_stream = MAPPING[network]
                            break
                if target_stream: break

        # 3. Exécution de la redirection
        if target_stream:
            # Code 302 pour indiquer au player que le contenu est temporairement ici
            return redirect(target_stream, code=302)
        else:
            # Fallback : Si rien ne joue, on envoie sur RDS
            return redirect(MAPPING["DEFAULT"], code=302)

    except Exception as e:
        # En cas d'erreur API, on ne bloque pas le player, on envoie le flux par défaut
        return redirect(MAPPING["DEFAULT"], code=302)

if __name__ == '__main__':
    app.run()
    
