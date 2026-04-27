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

@app.route('/nhl-live')
def redirect_to_nhl():
    # ... (Ta logique pour trouver target_stream) ...
    target_stream = target_stream or MAPPING["DEFAULT"]
    
    # Création d'une réponse de redirection manuelle
    response = make_response(redirect(target_stream, code=302))
    
    # ON FORCE LE TYPE DE CONTENU
    # Pour un lien .ts, on utilise video/mp2t. Pour un .m3u8, video/application/vnd.apple.mpegurl
    response.headers['Content-Type'] = 'video/mp2t'
    
    # ON SIMULE UN LECTEUR IPTV POUR LE SERVEUR
    response.headers['User-Agent'] = 'IPTVSmarters'
    
    # ON DIT AU LECTEUR DE NE PAS ENREGISTRER (TÉLÉCHARGER) LE FICHIER
    response.headers['Content-Disposition'] = 'inline'
    
    return response
