import xml.etree.ElementTree as ET
import requests
import json
import gzip
from io import BytesIO
from datetime import datetime, timedelta

# ==========================================
#                CONFIGURATION
# ==========================================

# IDs autorisés pour les sources standards
ALLOWED_CHANNELS = [
    "I123.15676.schedulesdirect.org", "I192.73271.schedulesdirect.org",
    "I124.39080.schedulesdirect.org", "I193.73142.schedulesdirect.org",
    "I1884.90206.schedulesdirect.org", "I405.62111.schedulesdirect.org",
    "I409.68858.schedulesdirect.org", "I410.49952.schedulesdirect.org",
    "I406.18798.schedulesdirect.org", "I408.18800.schedulesdirect.org",
    "I407.18801.schedulesdirect.org", "I401.18990.schedulesdirect.org",
    "I402.90118.schedulesdirect.org", "I403.90122.schedulesdirect.org",
    "I404.90124.schedulesdirect.org", "SNWorld",
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

# Sources EPG
URL_QUEBEC = "https://raw.githubusercontent.com/acidjesuz/EPGTalk/master/guide.xml"
URL_FRANCE = "https://xmltvfr.fr/xmltv/xmltv_fr.xml.gz"
URL_CA2 = "https://epgshare01.online/epgshare01/epg_ripper_CA2.xml.gz"

# ID spécifique pour One Soccer sur la nouvelle source
ID_ONESOCCER_CA2 = "One.Soccer.ca2"

# ==========================================
#                UTILITAIRES
# ==========================================

def is_within_3_days(date_str):
    if not date_str: return False
    try:
        # Nettoyage pour supporter les formats YYYYMMDDHHMMSS ou YYYYMMDDHHMM
        clean_date = date_str.split(' ')[0]
        fmt = "%Y%m%d%H%M%S" if len(clean_date) > 12 else "%Y%m%d%H%M"
        
        prog_date = datetime.strptime(clean_date, fmt)
        now = datetime.utcnow()
        return (now - timedelta(hours=24)) <= prog_date <= (now + timedelta(days=3))
    except:
        return False

# ==========================================
#                LOGIQUE PRINCIPALE
# ==========================================

def run():
    filtered_data = []
    allowed_set = set(ALLOWED_CHANNELS)
    
    print(f"--- DÉMARRAGE DE L'EXTRACTION ({datetime.utcnow().strftime('%H:%M:%S')} UTC) ---")

    # Configuration des sources : (Nom, URL, Zippé?, Filtre Spécifique)
    # Si le filtre est None, on utilise la liste ALLOWED_CHANNELS
    sources_config = [
        ("Québec/USA", URL_QUEBEC, False, allowed_set),
        ("France", URL_FRANCE, True, allowed_set),
        ("One Soccer CA2", URL_CA2, True, {ID_ONESOCCER_CA2})
    ]

    for name, url, is_zipped, current_filter in sources_config:
        try:
            print(f"Traitement source {name}...")
            r = requests.get(url, timeout=60)
            r.raise_for_status()
            
            input_data = gzip.GzipFile(fileobj=BytesIO(r.content)) if is_zipped else BytesIO(r.content)

            count = 0
            context = ET.iterparse(input_data, events=('end',))
            for _, elem in context:
                if elem.tag == 'programme':
                    ch_id = elem.get('channel')
                    start_time = elem.get('start')
                    
                    if ch_id in current_filter and is_within_3_days(start_time):
                        # On normalise l'ID de One Soccer pour le dictionnaire du proxy
                        final_id = "OneSoccer" if ch_id == ID_ONESOCCER_CA2 else ch_id
                        
                        filtered_data.append({
                            "ch": final_id,
                            "start": start_time,
                            "stop": elem.get('stop'),
                            "title": elem.findtext('title', 'Sport'),
                            "desc": elem.findtext('desc', ''),
                        })
                        count += 1
                    
                    elem.clear() # Libère la mémoire
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
    
