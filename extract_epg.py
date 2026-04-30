import xml.etree.ElementTree as ET
import requests
import json
import gzip
from io import BytesIO
from datetime import datetime, timedelta

# ==========================================
#                CONFIGURATION
# ==========================================

# On utilise les IDs de ton dictionnaire pour filtrer strictement
# Note : On garde les clés (ex: I123.15676.schedulesdirect.org) car c'est ce qui est dans le XML
ALLOWED_CHANNELS = [
    "I123.15676.schedulesdirect.org", "I192.73271.schedulesdirect.org",
    "I124.39080.schedulesdirect.org", "I193.73142.schedulesdirect.org",
    "I1884.90206.schedulesdirect.org", "I405.62111.schedulesdirect.org",
    "I409.68858.schedulesdirect.org", "I410.49952.schedulesdirect.org",
    "I406.18798.schedulesdirect.org", "I408.18800.schedulesdirect.org",
    "I407.18801.schedulesdirect.org", "I401.18990.schedulesdirect.org",
    "I402.90118.schedulesdirect.org", "I403.90122.schedulesdirect.org",
    "I404.90124.schedulesdirect.org", "OneSoccer", "SNWorld",
    "CanalPlus.fr", "CanalPlusSport.fr", "CanalPlusSport360.fr",
    "beINSPORTS1.fr", "BeInSports2.fr", "BeInSports3.fr",
    "BeInSportsMax4.fr", "BeInSportsMax5.fr", "BeInSportsMax6.fr",
    "BeInSportsMax7.fr", "BeInSportsMax8.fr", "BeInSportsMax9.fr",
    "BeInSportsMax10.fr", "Eurosport1.fr", "Eurosport2.fr",
    "RMCSport1.fr", "RMCSport2.fr", "L'Equipe", "TNTSports1",
    "TNTSports2", "TNTSports3", "SkySportsPremierLeague",
    "SkySportsF1", "PremierSports1", "PremierSports2",
    "FoxSports1", "CBSSportsNetwork", "BeInSportsUS", "ESPN", "ESPN2"
]

URL_QUEBEC = "https://raw.githubusercontent.com/acidjesuz/EPGTalk/master/guide.xml"
URL_FRANCE = "https://xmltvfr.fr/xmltv/xmltv_fr.xml.gz"

# ==========================================
#                UTILITAIRES
# ==========================================

def is_within_3_days(date_str):
    if not date_str: return False
    try:
        clean_date = date_str.split(' ')[0]
        prog_date = datetime.strptime(clean_date, "%Y%m%d%H%M%S")
        now = datetime.utcnow()
        # Fenêtre : 24h dans le passé à 3 jours dans le futur
        return (now - timedelta(hours=24)) <= prog_date <= (now + timedelta(days=3))
    except:
        return False

# ==========================================
#                LOGIQUE PRINCIPALE
# ==========================================

def run():
    filtered_data = []
    # On transforme en set pour une recherche ultra rapide (O(1))
    allowed_set = set(ALLOWED_CHANNELS)
    
    print(f"--- DÉMARRAGE DE L'EXTRACTION STRICTE ({datetime.utcnow().strftime('%H:%M:%S')} UTC) ---")

    # --- SOURCES (Quebec & France) ---
    sources = [("Québec/USA", URL_QUEBEC, False), ("France", URL_FRANCE, True)]

    for name, url, is_zipped in sources:
        try:
            print(f"Traitement source {name}...")
            r = requests.get(url, timeout=60)
            r.raise_for_status()
            
            if is_zipped:
                input_data = gzip.GzipFile(fileobj=BytesIO(r.content))
            else:
                input_data = BytesIO(r.content)

            count = 0
            # On utilise iterparse pour ne pas charger tout le XML en RAM
            context = ET.iterparse(input_data, events=('end',))
            for _, elem in context:
                if elem.tag == 'programme':
                    ch_id = elem.get('channel')
                    start_time = elem.get('start')
                    
                    # FILTRE STRICT : ID présent dans la liste ET date valide
                    if ch_id in allowed_set and is_within_3_days(start_time):
                        filtered_data.append({
                            "ch": ch_id,
                            "start": start_time,
                            "stop": elem.get('stop'),
                            "title": elem.findtext('title', 'Sport'),
                            "desc": elem.findtext('desc', ''),
                        })
                        count += 1
                    
                    # Nettoyage de la mémoire
                    elem.clear()
            print(f"-> {name} : {count} programmes retenus.")
            
        except Exception as e:
            print(f"Erreur source {name}: {e}")

    # --- SAUVEGARDE FINALE ---
    filtered_data.sort(key=lambda x: x['start'] if x['start'] else "")

    with open("filtered_epg.json", "w", encoding="utf-8") as f:
        json.dump(filtered_data, f, indent=2, ensure_ascii=False)
            
    print(f"--- TOTAL FINAL : {len(filtered_data)} programmes ---")

if __name__ == "__main__":
    run()
    
