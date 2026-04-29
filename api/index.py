import json
import os
from datetime import datetime

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
        "PENALTY_TVA": -150              # Juste pour préférer RDS si les deux sont là
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
#          POINT D'ENTRÉE (MAIN)
# ==========================================

def main():
    print("--- DÉMARRAGE DU SCOREUR D'ÉVÉNEMENTS ---")
    
    # 1. Chargement des données (assure-toi que les fichiers existent)
    try:
        with open('events.json', 'r', encoding='utf-8') as f:
            events = json.load(f)
        with open('filtered_epg.json', 'r', encoding='utf-8') as f:
            bible = json.load(f)
        print("Fichiers chargés avec succès.")
    except FileNotFoundError as e:
        print(f"Erreur : Fichier manquant ({e.filename})")
        return

    scored_list = []

    # 2. Attribution des scores
    for ev in events:
        name = ev.get('name', 'Inconnu')
        league = ev.get('league', 'autre')
        
        # On simule ici la récupération de la chaîne associée dans ton dictionnaire
        # Dans ton vrai code, tu utilises probablement 'find_match_in_bible'
        ch_key = ev.get('channel_id', 'Unknown') 
        lang = "FR" if "RDS" in str(ch_key) or "TVA" in str(ch_key) else "EN"

        score = calculate_score(name, league, ch_key, lang)
        
        scored_list.append({
            "name": name,
            "league": league,
            "channel": ch_key,
            "score": score
        })

    # 3. Tri par score décroissant
    final_output = sorted(scored_list, key=lambda x: x['score'], reverse=True)

    # 4. Sauvegarde ou Affichage
    with open('final_ranking.json', 'w', encoding='utf-8') as f:
        json.dump(final_output, f, indent=2, ensure_ascii=False)
    
    print(f"TERMINÉ : {len(final_output)} événements triés par priorité.")

if __name__ == "__main__":
    main()
    
