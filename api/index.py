from flask import Flask, jsonify
import json
import os
from datetime import datetime

app = Flask(__name__)

# ==========================================
#        CONFIGURATION DES PRIORITÉS
# ==========================================
PRIORITY_CONFIG = {
    "LEAGUES": {
        "nhl": 800,              
        "nba": 400, 
        "uefa.champions": 375,
        "eng.1": 350,
        "fra.1": 350,
        "mlb": 300
    },
    "TEAMS": {
        "CANADIENS": 3000,       # Priorité absolue
        "SENATORS": 1500,
        "MAPLE LEAFS": 1500,
        "RAPTORS": 1000, 
        "BLUE JAYS": 1000, 
        "CF MONTREAL": 1000
    },
    "CHANNELS": {
        "BONUS_HOCKEY_CANADA": 1000,     # RDS, TSN, SN
        "BONUS_FRENCH": 300,             
        "BONUS_ENGLISH_PREMIUM": 200,    
        "PENALTY_TVA": -150              # Départage vs RDS
    }
}

# IDs pour le bonus Hockey Canada
CANADA_HOCKEY_IDS = [
    "I1000.49609.schedulesdirect.org", "I192.73271.schedulesdirect.org", # RDS
    "I409.68858.schedulesdirect.org", "TSN2", "TSN3", "TSN4", "TSN5",    # TSN
    "I157674.schedulesdirect.org", "SNOne", "SN360", "SNEast", "SNOntario" # SN
]

TVA_SPORTS_IDS = ["I184811.schedulesdirect.org", "I193.73142.schedulesdirect.org"]

# ==========================================
#           LOGIQUE DE SCORING
# ==========================================

def calculate_score(event_name, league, ch_key, lang):
    score = PRIORITY_CONFIG["LEAGUES"].get(league, 100)
    
    # Bonus Équipes
    for team, bonus in PRIORITY_CONFIG["TEAMS"].items():
        if team.upper() in event_name.upper():
            score += bonus
            
    # Bonus Hockey Canada
    if league == "nhl" and ch_key in CANADA_HOCKEY_IDS:
        score += PRIORITY_CONFIG["CHANNELS"]["BONUS_HOCKEY_CANADA"]
        
    # Bonus Langue
    if lang == "FR":
        score += PRIORITY_CONFIG["CHANNELS"]["BONUS_FRENCH"]
        
    # Pénalité TVA
    if ch_key in TVA_SPORTS_IDS:
        score += PRIORITY_CONFIG["CHANNELS"]["PENALTY_TVA"]
        
    return score

# ==========================================
#                ROUTES FLASK
# ==========================================

@app.route('/')
def get_events():
    try:
        # 1. Chargement des données
        if not os.path.exists('events.json') or not os.path.exists('filtered_epg.json'):
            return jsonify({"error": "Fichiers de données manquants"}), 500

        with open('events.json', 'r', encoding='utf-8') as f:
            events = json.load(f)
        
        scored_list = []

        # 2. Attribution des scores et tri
        for ev in events:
            name = ev.get('name', 'Inconnu')
            league = ev.get('league', 'autre')
            ch_key = ev.get('channel_id', 'Unknown')
            
            # Détection simple de la langue pour le score
            lang = "FR" if any(x in str(ch_key) for x in ["RDS", "TVA", ".fr"]) else "EN"

            ev['score'] = calculate_score(name, league, ch_key, lang)
            scored_list.append(ev)

        # 3. Tri par score décroissant
        final_output = sorted(scored_list, key=lambda x: x.get('score', 0), reverse=True)

        return jsonify(final_output)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==========================================
#            LANCEMENT DU SERVEUR
# ==========================================

if __name__ == "__main__":
    # Écoute sur toutes les interfaces (0.0.0.0) sur le port 5000
    app.run(host='0.0.0.0', port=5000, debug=True)
    
