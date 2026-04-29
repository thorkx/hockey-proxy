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
        "CANADIENS": 3000,       # Priorité absolue pour le CH
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
        "PENALTY_TVA": -150              # Juste assez pour préférer RDS
    }
}

# IDs pour le bonus Hockey Canada (RDS, TSN, SN)
CANADA_HOCKEY_IDS = [
    "I1000.49609.schedulesdirect.org", "I192.73271.schedulesdirect.org", # RDS 1-2
    "I409.68858.schedulesdirect.org", "TSN2", "TSN3", "TSN4", "TSN5",    # TSN
    "I157674.schedulesdirect.org", "SNOne", "SN360", "SNEast", "SNOntario" # SN
]

TVA_SPORTS_IDS = ["I184811.schedulesdirect.org", "I193.73142.schedulesdirect.org"]

# ==========================================
#           LOGIQUE DE SCORING
# ==========================================

def calculate_score(event_name, league, ch_key):
    score = PRIORITY_CONFIG["LEAGUES"].get(league, 100)
    
    # 1. Bonus Équipes (Canadiens, etc.)
    for team, bonus in PRIORITY_CONFIG["TEAMS"].items():
        if team.upper() in event_name.upper():
            score += bonus
            
    # 2. Bonus Hockey Canada
    if league == "nhl" and ch_key in CANADA_HOCKEY_IDS:
        score += PRIORITY_CONFIG["CHANNELS"]["BONUS_HOCKEY_CANADA"]
        
    # 3. Bonus Langue (Détection par ID ou nom)
    # Si l'ID contient .fr ou si c'est RDS/TVA
    if any(x in str(ch_key).lower() for x in ["rds", "tva", ".fr"]):
        score += PRIORITY_CONFIG["CHANNELS"]["BONUS_FRENCH"]
    elif ch_key in CANADA_HOCKEY_IDS or "sky" in str(ch_key).lower():
        score += PRIORITY_CONFIG["CHANNELS"]["BONUS_ENGLISH_PREMIUM"]
        
    # 4. Pénalité TVA Sports
    if ch_key in TVA_SPORTS_IDS:
        score += PRIORITY_CONFIG["CHANNELS"]["PENALTY_TVA"]
        
    return score

# ==========================================
#                ROUTE API
# ==========================================

@app.route('/')
def get_events():
    try:
        # Détermination des chemins absolus
        base_dir = os.path.dirname(os.path.abspath(__file__))
        events_path = os.path.join(base_dir, 'events.json')
        epg_path = os.path.join(base_dir, 'filtered_epg.json')

        # Vérification de l'existence des fichiers
        if not os.path.exists(events_path):
            return jsonify({"error": f"Fichier {events_path} introuvable"}), 500
        if not os.path.exists(epg_path):
            return jsonify({"error": f"Fichier {epg_path} introuvable"}), 500

        # Chargement des données
        with open(events_path, 'r', encoding='utf-8') as f:
            events = json.load(f)
        
        scored_list = []

        # Attribution des scores
        for ev in events:
            name = ev.get('name', 'Événement')
            league = ev.get('league', 'autre')
            ch_key = ev.get('channel_id', 'Unknown')

            # Calcul du score basé sur tes nouvelles priorités
            ev['priority_score'] = calculate_score(name, league, ch_key)
            scored_list.append(ev)

        # Tri par score décroissant (les plus gros scores en premier)
        final_output = sorted(scored_list, key=lambda x: x.get('priority_score', 0), reverse=True)

        return jsonify(final_output)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==========================================
#            LANCEMENT SERVEUR
# ==========================================

if __name__ == "__main__":
    # Écoute sur le port 5000
    # host='0.0.0.0' permet l'accès depuis d'autres appareils sur ton réseau
    app.run(host='0.0.0.0', port=5000, debug=True)
