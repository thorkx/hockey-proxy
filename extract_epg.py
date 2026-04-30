import xml.etree.ElementTree as ET
import requests
import json
import gzip
from io import BytesIO
from datetime import datetime, timedelta

# ==========================================
#                CONFIGURATION
# ==========================================

# Liste synchronisée avec ton dictionnaire CH_DATABASE
ALLOWED_CHANNELS = [
    # Canada
    "I123.15676.schedulesdirect.org", "I192.73271.schedulesdirect.org",
    "I124.39080.schedulesdirect.org", "I193.73142.schedulesdirect.org",
    "I1884.90206.schedulesdirect.org", "I405.62111.schedulesdirect.org",
    "I409.68858.schedulesdirect.org", "I410.49952.schedulesdirect.org",
    "I406.18798.schedulesdirect.org", "I408.18800.schedulesdirect.org",
    "I407.18801.schedulesdirect.org", "I401.18990.schedulesdirect.org",
    "I402.90118.schedulesdirect.org", "I403.90122.schedulesdirect.org",
    "I404.90124.schedulesdirect.org", "I420.57735.schedulesdirect.org",
    
    # France
    "CanalPlus.fr", "CanalPlusSport.fr", "CanalPlusSport360.fr",
    "beINSPORTS1.fr", "beINSPORTS2.fr", "beINSPORTS3.fr",
    "beINSPORTSMAX4.fr", "beINSPORTSMAX5.fr", "beINSPORTSMAX6.fr",
    "beINSPORTSMAX7.fr", "beINSPORTSMAX8.fr", "beINSPORTSMAX9.fr",
    "beINSPORTSMAX10.fr", "Eurosport1.fr", "Eurosport2.fr",
    "RMCSport1.fr", "RMCSport2.fr",
    
    # UK
    "I1241.82450.schedulesdirect.org", "I1246.82451.schedulesdirect.org",
    "I1248.95772.schedulesdirect.org", "I1099.116645.schedulesdirect.org",
    "I1081.87578.schedulesdirect.org",
    
    # USA
    "I206.32645.schedulesdirect.org", "I209.45507.schedulesdirect.org",
    "I301.25595.schedulesdirect.org", "I219.82541.schedulesdirect.org",
    "I221.16365.schedulesdirect.org", "I392.76942.gracenote.com"
]

# Sources EPG
URL_QUEBEC = "https://raw.githubusercontent.com/acidjesuz/EPGTalk/master/guide.xml"
URL_FRANCE = "https://xmltvfr.fr/xmltv/xmltv_fr.xml.gz"
URL_CA2 = "https://epgshare01.online/epgshare01/epg_ripper_CA2.xml.gz"

# ID spécifique pour One Soccer sur la source CA2
ID_ONESOCCER_CA2 = "One.Soccer.ca2"

# ==========================================
#                UTILITAIRES
# ==========================================

def is_within_3_days(date_str):
    if not date_str: return False
    try:
        clean_date = date_str.split(' ')[0]
        # Support pour formats YYYYMMDDHHMMSS ou YYYYMMDDHHMM
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

    # (Nom, URL, Zippé?, Filtre)
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
                        # Normalisation de l'ID One Soccer pour matcher ton CH_DATABASE
                        final_id = ch_id # Garde l'id tel quel pour matcher ton dictionnaire
                        
                        filtered_data.append({
                            "ch": final_id,
                            "start": start_time,
                            "stop": elem.get('stop'),
                            "title": elem.findtext('title', 'Sport'),
                            "desc": elem.findtext('desc', ''),
                        })
                        count += 1
                    
                    elem.clear()
            print(f"-> {name} : {count} programmes retenus.")
            
        except Exception as e:
            print(f"Erreur source {name}: {e}")

    # Tri final par date
    filtered_data.sort(key=lambda x: x['start'] if x['start'] else "")

    with open("filtered_epg.json", "w", encoding="utf-8") as f:
        json.dump(filtered_data, f, indent=2, ensure_ascii=False)
            
    print(f"--- TOTAL FINAL : {len(filtered_data)} programmes ---")

if __name__ == "__main__":
    run()
    
