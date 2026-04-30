import xml.etree.ElementTree as ET
import requests
import json
import gzip
from io import BytesIO
from datetime import datetime, timedelta

# ==========================================
#                CONFIGURATION
# ==========================================

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

URL_QUEBEC = "https://raw.githubusercontent.com/acidjesuz/EPGTalk/master/guide.xml"
URL_FRANCE = "https://xmltvfr.fr/xmltv/xmltv_fr.xml.gz"
URL_CA2 = "https://epgshare01.online/epgshare01/epg_ripper_CA2.xml.gz"
ID_ONESOCCER_CA2 = "One.Soccer.ca2"

HL_KEYWORDS = ["RÉSUMÉ", "HIGHLIGHTS", "REPRISE", "CLASSIC", "REVUE", "TOP 10", "MAGAZINE", "DEBRIEF"]

# --- NOUVELLE CONFIGURATION DE FILTRAGE ---
MIN_DURATION_MINUTES = 60
EXCEPTIONS_TITLES = ["SC"] # Liste des titres à garder même si < 60 min

# ==========================================
#                UTILITAIRES
# ==========================================

def get_duration_minutes(start_str, stop_str):
    """Calcule la durée entre start et stop en minutes"""
    try:
        fmt = "%Y%m%d%H%M%S" if len(start_str.split()[0]) > 12 else "%Y%m%d%H%M"
        t1 = datetime.strptime(start_str.split()[0], fmt)
        t2 = datetime.strptime(stop_str.split()[0], fmt)
        return (t2 - t1).total_seconds() / 60
    except:
        return 0

def is_within_3_days(date_str):
    if not date_str: return False
    try:
        clean_date = date_str.split(' ')[0]
        fmt = "%Y%m%d%H%M%S" if len(clean_date) > 12 else "%Y%m%d%H%M"
        prog_date = datetime.strptime(clean_date, fmt)
        now = datetime.utcnow()
        # Fenêtre élargie pour couvrir le weekend (48h passé, 4 jours futur)
        return (now - timedelta(hours=48)) <= prog_date <= (now + timedelta(days=4))
    except:
        return False

# ==========================================
#                LOGIQUE PRINCIPALE
# ==========================================

def run():
    filtered_data = []
    allowed_set = set(ALLOWED_CHANNELS)
    exceptions_set = set(EXCEPTIONS_TITLES)
    
    print(f"--- DÉMARRAGE DE L'EXTRACTION ({datetime.utcnow().strftime('%H:%M:%S')} UTC) ---")

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
                    stop_time = elem.get('stop')
                    
                    if ch_id in current_filter and is_within_3_days(start_time):
                        title = elem.findtext('title', 'Sport')
                        
                        # --- LOGIQUE DE FILTRAGE DURÉE ET EXCEPTIONS ---
                        duration = get_duration_minutes(start_time, stop_time)
                        
                        if duration >= MIN_DURATION_MINUTES or title in exceptions_set:
                            desc = elem.findtext('desc', '')
                            # Récupération enrichie des sous-titres et catégories
                            subtitle = elem.findtext('sub-title', '')
                            category = elem.findtext('category', '')
                            
                            content_upper = (title + " " + subtitle + " " + desc).upper()
                            is_hl = any(kw in content_upper for kw in HL_KEYWORDS)
                            
                            filtered_data.append({
                                "ch": ch_id,
                                "start": start_time,
                                "stop": stop_time,
                                "title": title,
                                "sub-title": subtitle,
                                "desc": desc,
                                "category": category,
                                "is_highlight": is_hl
                            })
                            count += 1
                    
                    elem.clear()
            print(f"-> {name} : {count} programmes retenus.")
            
        except Exception as e:
            print(f"Erreur source {name}: {e}")

    filtered_data.sort(key=lambda x: x['start'] if x['start'] else "")

    with open("filtered_epg.json", "w", encoding="utf-8") as f:
        json.dump(filtered_data, f, indent=2, ensure_ascii=False)
            
    print(f"--- TOTAL FINAL : {len(filtered_data)} programmes ---")

if __name__ == "__main__":
    run()
            
