import json
from datetime import datetime

# ==========================================
#        CONFIGURATION DES PRIORITÉS
# ==========================================
PRIORITY_CONFIG = {
    "LEAGUES": {
        "nhl": 800,              # Augmenté pour dominer le reste
        "nba": 400, 
        "uefa.champions": 375,
        "eng.1": 350,
        "fra.1": 350,
        "mlb": 300,
        "usa.1": 250
    },
    "TEAMS": {
        "CANADIENS": 3000,       # Score massif : Priorité absolue
        "SENATORS": 1500,
        "MAPLE LEAFS": 1500,
        "RAPTORS": 1000, 
        "BLUE JAYS": 1000, 
        "CF MONTREAL": 1000
    },
    "CHANNELS": {
        "BONUS_HOCKEY_CANADA": 1000,     # Bonus RDS, TSN, SN pour le hockey
        "BONUS_FRENCH": 300,             # Prédilection pour le français
        "BONUS_ENGLISH_PREMIUM": 200,    # Petit bonus pour SN/TSN vs ESPN
        "PENALTY_TVA": -150              # Pénalité légère (départage vs RDS)
    }
}

# IDs des chaînes Canadiennes pour le bonus Hockey
CANADA_HOCKEY_IDS = [
    "I1000.49609.schedulesdirect.org", "I192.73271.schedulesdirect.org", # RDS 1-2
    "I409.68858.schedulesdirect.org", "TSN2", "TSN3", "TSN4", "TSN5",    # TSN
    "I157674.schedulesdirect.org", "SNOne", "SN360", "SNEast", "SNOntario", "SNWest", "SNPacific" # SN
]

# IDs spécifiques TVA Sports (pour la pénalité de départage)
TVA_SPORTS_IDS = ["I184811.schedulesdirect.org", "I193.73142.schedulesdirect.org"]

# ==========================================
#           LOGIQUE DE SCORING
# ==========================================

def calculate_event_score(event_name, league, ch_key, ch_lang):
    score = PRIORITY_CONFIG["LEAGUES"].get(league, 100)
    
    # 1. Priorité Équipes (Canadiens en tête)
    for team, bonus in PRIORITY_CONFIG["TEAMS"].items():
        if team.upper() in event_name.upper():
            score += bonus
            
    # 2. Priorité Hockey Canadien (RDS/SN/TSN vs USA/FR)
    if league == "nhl" and ch_key in CANADA_HOCKEY_IDS:
        score += PRIORITY_CONFIG["CHANNELS"]["BONUS_HOCKEY_CANADA"]
        
    # 3. Préférence Linguistique
    if ch_lang == "FR":
        score += PRIORITY_CONFIG["CHANNELS"]["BONUS_FRENCH"]
        
    # 4. Pénalité TVA Sports (départage léger)
    if ch_key in TVA_SPORTS_IDS:
        score += PRIORITY_CONFIG["CHANNELS"]["PENALTY_TVA"]
        
    return score

def get_organized_events(api_data, bible):
    organized = []
    
    for ev in api_data:
        name = ev.get('name', 'Événement')
        league = ev.get('league', 'autre')
        
        # On cherche la meilleure source dans la bible EPG
        best_ch_key = None
        best_score = -9999
        
        # Simulation de la recherche de canal (basé sur ton dictionnaire de postes)
        # Ici on boucle sur les canaux possibles pour cet événement
        for ch_key, info in CH_DATABASE.items():
            # (Logique de matching entre l'event et le guide EPG ici...)
            # ...
            
            current_score = calculate_event_score(name, league, ch_key, info.get('lang'))
            
            if current_score > best_score:
                best_score = current_score
                best_ch_key = ch_key
        
        organized.append({
            "event": name,
            "league": league,
            "channel_id": best_ch_key,
            "score": best_score
        })
    
    # Tri final par score décroissant
    return sorted(organized, key=lambda x: x['score'], reverse=True)

# ==========================================
#            BASE DE DONNÉES POSTES
# ==========================================
# (Extrait de ton fichier ListePostes.txt)
CH_DATABASE = {
    "I1000.49609.schedulesdirect.org": {"name": "RDS", "lang": "FR"},
    "I184811.schedulesdirect.org": {"name": "TVA Sports", "lang": "FR"},
    "I71518.schedulesdirect.org": {"name": "Sportsnet East", "lang": "EN"},
    # ... etc
}
