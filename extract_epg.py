import xml.etree.ElementTree as ET
import requests
import json
from io import BytesIO

def run():
    url = "https://raw.githubusercontent.com/acidjesuz/EPGTalk/master/guide.xml"
    KEYWORDS = ["RDS", "TSN", "SPORTSNET", "SN ", "TVA SPORTS", "CANAL+", "BEIN", "DAZN"]
    
    try:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        
        # Utilisation de iterparse pour sauver la RAM
        context = ET.iterparse(BytesIO(r.content), events=('start', 'end'))
        target_ids = set()
        filtered_data = []

        # 1. Identifier les chaînes
        for event, elem in context:
            if event == 'end' and elem.tag == 'channel':
                ch_id = elem.get('id')
                names = [dn.text.upper() for dn in elem.findall('display-name') if dn.text]
                if any(any(kw in name for kw in KEYWORDS) for name in names):
                    target_ids.add(ch_id)
                elem.clear()

        # 2. Extraire les programmes (on recharge le flux)
        context = ET.iterparse(BytesIO(r.content), events=('start', 'end'))
        for event, elem in context:
            if event == 'end' and elem.tag == 'programme':
                ch_id = elem.get('channel')
                if ch_id in target_ids:
                    title = elem.find('title').text if elem.find('title') is not None else "Match"
                    filtered_data.append({
                        "ch": ch_id,
                        "start": elem.get('start'),
                        "title": title
                    })
                elem.clear()

        with open('filtered_epg.json', 'w', encoding='utf-8') as f:
            json.dump(filtered_data, f, ensure_ascii=False)
        print(f"Extraction réussie : {len(filtered_data)} items.")

    except Exception as e:
        print(f"Erreur : {e}")
        # On ne quitte pas avec exit(1) pour laisser le JSON vide si ça rate 
        # plutôt que de faire échouer l'action violemment

if __name__ == "__main__":
    run()
    
