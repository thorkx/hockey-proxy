from flask import Flask, redirect
import requests

app = Flask(__name__)

# ==========================================
# TA CONFIGURATION (À REMPLIR)
# ==========================================
# Remplace les URLs ci-dessous par tes liens IPTV réels (ceux qui finissent par .ts ou .m3u8)
MAPPING = {
    "RDS": "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV/184813.ts",
    "TVAS": "http://ton-serveur.com:8080/user/pass/ID_TVAS.ts",
    "SN": "http://ton-serveur.com:8080/user/pass/ID_SN.ts",
    "SNE": "http://ton-serveur.com:8080/user/pass/ID_SN_EAST.ts",
    "CBC": "http://ton-serveur.com:8080/user/pass/ID_CBC.ts",
    "DEFAULT": "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV/184813.ts" # Ton RDS par défaut
}

FAVORITES = ["MTL", "COL", "PHI", "PIT"]

@app.route('/')
def home():
    return "NHL Proxy is running. Use /nhl-live to get the stream."

@app.route('/nhl-live')
def redirect_to_nhl():
    try:
        # 1. On interroge l'API des scores (plus précis pour le "live")
        url = "https://api-web.nhle.com/v1/score/now"
        response = requests.get(url, timeout=5)
        data = response.json()
        
        target_stream = None

        # 2. On cherche si un de tes favoris joue
        for game in data.get('games', []):
            away = game['awayTeam']['abbrev']
            home = game['homeTeam']['abbrev']
            
            if home in FAVORITES or away in FAVORITES:
                # On vérifie si le match est commencé ou imminent (Pre-game ou In-Progress)
                # gameState 2 = Pre-game, 3 = In-progress
                if game.get('gameState') in ["PRE", "LIVE", "CRIT"]:
                    tv_list = game.get('tvBroadcasts', [])
                    # On cherche le premier poste canadien disponible
                    ca_tv = [tv['network'] for tv in tv_list if tv['countryCode'] == 'CA']
                    
                    if ca_tv:
                        poste_id = ca_tv[0]
                        target_stream = MAPPING.get(poste_id)
                        if target_stream:
                            break # On a trouvé notre match prioritaire

        # 3. Redirection
        if target_stream:
            return redirect(target_stream, code=302)
        else:
            # Aucun match favori en cours -> Redirection vers RDS par défaut
            return redirect(MAPPING["DEFAULT"], code=302)

    except Exception as e:
        print(f"Erreur: {e}")
        return redirect(MAPPING["DEFAULT"], code=302)
      
