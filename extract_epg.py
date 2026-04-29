import xml.etree.ElementTree as ET
import requests
import json
from io import BytesIO

# On garde une liste large, c'est Vercel qui fera le tri final
KEYWORDS = ["RDS", "TSN", "SPORTSNET", "SN ", "TVA SPORTS", "CANAL+", "BEIN", "DAZN", "SKY SPORTS", "TNT SPORTS", "EUROSPORT"]

def run():
    url = "https://raw.githubusercontent.com/acidjesuz/EPGTalk/master/guide.xml"
    print("--- DÉMARRAGE DE L'EXTRACTION COMPLÈTE ---")
    
    try:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        xml_data = BytesIO(r.content)
        
        target_ids = {} 
        filtered_data = []

        # PASSAGE 1 : On identifie les chaînes (inchangé, c'est efficace)
        context = ET.iterparse(xml_data, events=('end',))
        for _, elem in context:
            if elem.tag == 'channel':
                ch_id = elem.get('id')
                names = [dn.text for dn in elem.findall('display-name') if dn.text]
                if any(any(kw.upper() in name.upper() for kw in KEYWORDS) for name in names):
                    target_ids[ch_id] = names[0]
                elem.clear()
        
        # PASSAGE 2 : On extrait TOUTES les infos du programme
        xml_data.seek(0)
        context = ET.iterparse(xml_data, events=('end',))
        for _, elem in context:
            if elem.tag == 'programme':
                ch_id = elem.get('channel')
                
                if ch_id in target_ids:
                    # Extraction enrichie
                    title = elem.findtext('title', 'Événement Sportif')
                    desc = elem.findtext('desc', '')
                    category = elem.findtext('category', '')
                    
                    filtered_data.append({
                        "ch": ch_id,
                        "name": target_ids[ch_id],
                        "start": elem.get('start'),
                        "stop": elem.get('stop'), # CRITIQUE pour la régie anti-conflit
                        "title": title,
                        "desc": desc,         # Utile pour chercher "Canadiens" si c'est pas dans le titre
                        "cat": category
                    })
                elem.clear()

        # Sauvegarde du JSON complet sur GitHub
        with open("filtered_epg.json", "w", encoding="utf-8") as f:
            json.dump(filtered_data, f, indent=2, ensure_ascii=False)
            
        print(f"Extraction réussie : {len(filtered_data)} programmes enrichis.")

    except Exception as e:
        print(f"Erreur bot: {e}")

if __name__ == "__main__":
    run()
    
