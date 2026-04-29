import xml.etree.ElementTree as ET
import requests
import json
import gzip
from io import BytesIO

# Liste élargie pour inclure les variantes françaises
KEYWORDS = ["RDS", "TSN", "SPORTSNET", "SN ", "TVA SPORTS", "CANAL+", "BEIN", "DAZN", "SKY SPORTS", "TNT SPORTS", "EUROSPORT", "RMC SPORT"]

def run():
    # Sources
    URL_QUEBEC = "https://raw.githubusercontent.com/acidjesuz/EPGTalk/master/guide.xml"
    URL_FRANCE = "https://xmltvfr.fr/xmltv/xmltv_fr.xml.gz"
    
    filtered_data = []
    print("--- DÉMARRAGE DE L'EXTRACTION MULTI-SOURCES ---")
    
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
                if ch_id in target_ids:
                    filtered_data.append({
                        "ch": ch_id,
                        "name": target_ids[ch_id],
                        "start": elem.get('start'),
                        "stop": elem.get('stop'),
                        "title": elem.findtext('title', 'Événement Sportif'),
                        "desc": elem.findtext('desc', ''),
                        "cat": elem.findtext('category', '')
                    })
                elem.clear()
        print(f"AcidJesuz: {len(filtered_data)} programmes ajoutés.")
    except Exception as e:
        print(f"Erreur source Québec: {e}")

    # --- PARTIE 2 : FRANCE (Racacax / xmltvfr) ---
    try:
        print("Récupération source France (Racacax)...")
        r_fr = requests.get(URL_FRANCE, timeout=60)
        r_fr.raise_for_status()
        
        # Décompression du .gz en mémoire
        with gzip.GzipFile(fileobj=BytesIO(r_fr.content)) as decompressor:
            xml_france = decompressor.read()
        
        fr_data = BytesIO(xml_france)
        fr_target_ids = {}

        # Passage 1 : Identification des chaînes sportives FR
        context = ET.iterparse(fr_data, events=('end',))
        for _, elem in context:
            if elem.tag == 'channel':
                ch_id = elem.get('id')
                names = [dn.text for dn in elem.findall('display-name') if dn.text]
                # On filtre par nos KEYWORDS sportifs
                if any(any(kw.upper() in name.upper() for kw in KEYWORDS) for name in names):
                    fr_target_ids[ch_id] = names[0]
                elem.clear()
        
        # Passage 2 : Programmes FR
        fr_data.seek(0)
        count_fr = 0
        context = ET.iterparse(fr_data, events=('end',))
        for _, elem in context:
            if elem.tag == 'programme':
                ch_id = elem.get('channel')
                if ch_id in fr_target_ids:
                    filtered_data.append({
                        "ch": ch_id, # Ex: CanalPlus.fr
                        "name": fr_target_ids[ch_id],
                        "start": elem.get('start'),
                        "stop": elem.get('stop'),
                        "title": elem.findtext('title', 'Sport'),
                        "desc": elem.findtext('desc', ''),
                        "cat": elem.findtext('category', 'Sport')
                    })
                    count_fr += 1
                elem.clear()
        print(f"France: {count_fr} programmes ajoutés.")
    except Exception as e:
        print(f"Erreur source France: {e}")

    # --- SAUVEGARDE FINALE ---
    with open("filtered_epg.json", "w", encoding="utf-8") as f:
        json.dump(filtered_data, f, indent=2, ensure_ascii=False)
            
    print(f"TOTAL : {len(filtered_data)} programmes dans le JSON final.")

if __name__ == "__main__":
    run()
    
