import xml.etree.ElementTree as ET
import requests
import json
import gzip
from io import BytesIO
from datetime import datetime, timedelta

# ==========================================
#                CONFIGURATION
# ==========================================

# Liste élargie pour couvrir Canada, USA, UK et France
KEYWORDS = [
    # Canada
    "RDS", "TSN", "TVA SPORTS", "SN ", "SPORTSNET", "ONESOCCER",
    
    # USA
    "ESPN", "CBS SPORTS", "FOX SPORTS", "FS1", "FS2", "GOLAZO", 
    "MARQUEE SPORTS", "MSG ", "YES NETWORK", "NBC SPORTS",
    
    # UK / Europe
    "SKY SPORT", "TNT SPORT", "EUROSPORT", "VIAPLAY", "PREMIER SPORT",
    
    # France
    "CANAL+", "CANAL +", "BEIN", "RMC SPORT", "L'EQUIPE", "DAZN"
]

URL_QUEBEC = "https://raw.githubusercontent.com/acidjesuz/EPGTalk/master/guide.xml"
URL_FRANCE = "https://xmltvfr.fr/xmltv/xmltv_fr.xml.gz"

# ==========================================
#                UTILITAIRES
# ==========================================

def is_within_3_days(date_str):
    """Vérifie si la date du programme est pertinente (Fenêtre assouplie)"""
    if not date_str:
        return False
    try:
        # Format XMLTV : 20240520143000 +0000
        clean_date = date_str.split(' ')[0]
        prog_date = datetime.strptime(clean_date, "%Y%m%d%H%M%S")
        
        # Utilisation de UTC pour la compatibilité avec les sources XMLTV
        now = datetime.utcnow()
        
        # LIMITE PASSÉE : 24h avant pour ne rien louper des matchs de nuit ou en cours
        start_limit = now - timedelta(hours=24)
        
        # LIMITE FUTURE : 3 jours complets
        end_limit = now + timedelta(days=3)
        
        return start_limit <= prog_date <= end_limit
    except:
        return False

# ==========================================
#                LOGIQUE PRINCIPALE
# ==========================================

def run():
    filtered_data = []
    print(f"--- DÉMARRAGE DE L'EXTRACTION ({datetime.utcnow().strftime('%H:%M:%S')} UTC) ---")

    # --- PARTIE 1 : QUÉBEC / USA (AcidJesuz) ---
    try:
        print("Récupération source AcidJesuz...")
        r = requests.get(URL_QUEBEC, timeout=60)
        r.raise_for_status()
        xml_data = BytesIO(r.content)
        
        target_ids = {}
        # Passage 1 : Identification
        context = ET.iterparse(xml_data, events=('end',))
        for _, elem in context:
            if elem.tag == 'channel':
                ch_id = elem.get('id')
                names = [dn.text for dn in elem.findall('display-name') if dn.text]
                if any(any(kw.upper() in name.upper() for kw in KEYWORDS) for name in names):
                    target_ids[ch_id] = names[0]
                elem.clear()
        
        # Passage 2 : Programmes
        xml_data.seek(0)
        context = ET.iterparse(xml_data, events=('end',))
        for _, elem in context:
            if elem.tag == 'programme':
                ch_id = elem.get('channel')
                start_time = elem.get('start')
                if ch_id in target_ids and is_within_3_days(start_time):
                    filtered_data.append({
                        "ch": ch_id,
                        "display_name": target_ids[ch_id],
                        "start": start_time,
                        "stop": elem.get('stop'),
                        "title": elem.findtext('title', 'Sport'),
                        "desc": elem.findtext('desc', ''),
                    })
                elem.clear()
        print(f"AcidJesuz : Terminé ({len(filtered_data)} programmes).")
    except Exception as e:
        print(f"Erreur source Québec: {e}")

    # --- PARTIE 2 : FRANCE (xmltvfr - Stream compressé) ---
    try:
        print("Récupération source France (xmltvfr)...")
        r_fr = requests.get(URL_FRANCE, timeout=60, stream=True)
        r_fr.raise_for_status()
        
        with gzip.GzipFile(fileobj=BytesIO(r_fr.content)) as decompressor:
            fr_target_ids = {}
            count_fr = 0
            context = ET.iterparse(decompressor, events=('end',))
            for _, elem in context:
                if elem.tag == 'channel':
                    ch_id = elem.get('id')
                    names = [dn.text for dn in elem.findall('display-name') if dn.text]
                    if any(any(kw.upper() in name.upper() for kw in KEYWORDS) for name in names):
                        fr_target_ids[ch_id] = names[0]
                    elem.clear()
                
                elif elem.tag == 'programme':
                    ch_id = elem.get('channel')
                    start_time = elem.get('start')
                    if ch_id in fr_target_ids and is_within_3_days(start_time):
                        filtered_data.append({
                            "ch": ch_id,
                            "display_name": fr_target_ids[ch_id],
                            "start": start_time,
                            "stop": elem.get('stop'),
                            "title": elem.findtext('title', 'Sport'),
                            "desc": elem.findtext('desc', ''),
                        })
                        count_fr += 1
                    elem.clear()
            print(f"France : Terminé ({count_fr} programmes ajoutés).")
    except Exception as e:
        print(f"Erreur source France: {e}")

    # --- SAUVEGARDE FINALE ---
    filtered_data.sort(key=lambda x: x['start'] if x['start'] else "")

    with open("filtered_epg.json", "w", encoding="utf-8") as f:
        json.dump(filtered_data, f, indent=2, ensure_ascii=False)
            
    print(f"--- TOTAL : {len(filtered_data)} programmes dans filtered_epg.json ---")

if __name__ == "__main__":
    run()
    
