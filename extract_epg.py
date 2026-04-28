import xml.etree.ElementTree as ET
import requests
import json
from io import BytesIO

KEYWORDS = ["RDS", "TSN", "SPORTSNET", "SN ", "TVA SPORTS", "CANAL+", "BEIN", "DAZN", "SKY SPORTS"]

def run():
    url = "https://raw.githubusercontent.com/acidjesuz/EPGTalk/master/guide.xml"
    print("Début du téléchargement...")
    
    try:
        response = requests.get(url, timeout=60)
        if response.status_code != 200:
            print(f"Erreur HTTP : {response.status_code}")
            exit(1)

        # On utilise BytesIO pour simuler un fichier en mémoire
        xml_file = BytesIO(response.content)
        
        target_ids = set()
        filtered_data = []

        # Premier passage : Identifier les chaînes par Display Name
        context = ET.iterparse(xml_file, events=('start', 'end'))
        for event, elem in context:
            if event == 'end' and elem.tag == 'channel':
                ch_id = elem.get('id')
                names = [dn.text.upper() for dn in elem.findall('display-name') if dn.text]
                if any(any(kw in name for kw in KEYWORDS) for name in names):
                    target_ids.add(ch_id)
                elem.clear() # Libère la mémoire

        print(f"Chaînes trouvées : {len(target_ids)}")
        
        # Second passage : Extraire les programmes
        xml_file.seek(0) # On revient au début du fichier
        context = ET.iterparse(xml_file, events=('start', 'end'))
        for event, elem in context:
            if event == 'end' and elem.tag == 'programme':
                ch_id = elem.get('channel')
                if ch_id in target_ids:
                    title_node = elem.find('title')
                    title = title_node.text if title_node is not None else "Match"
                    
                    filtered_data.append({
                        "ch": ch_id,
                        "start": elem.get('start'),
                        "title": title
                    })
                elem.clear() # Libère la mémoire

        print(f"Total programmes : {len(filtered_data)}")
        with open('filtered_epg.json', 'w', encoding='utf-8') as f:
            json.dump(filtered_data, f, ensure_ascii=False)
            
    except Exception as e:
        print(f"CRASH : {e}")
        exit(1) # Force l'échec pour voir l'erreur dans les logs GitHub

if __name__ == "__main__":
    run()
    
