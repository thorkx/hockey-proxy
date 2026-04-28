import xml.etree.ElementTree as ET
import requests
import json

# On définit des mots-clés simples à trouver dans les <display-name>
KEYWORDS_TO_KEEP = [
    "RDS", "TSN", "Sportsnet", "SN East", "SN One", "TVA Sports", 
    "Canal+", "BeIN Sports", "DAZN", "Sky Sports", "TNT Sports"
]

def run():
    url = "https://raw.githubusercontent.com/acidjesuz/EPGTalk/master/guide.xml"
    print("Téléchargement de l'EPG source...")
    
    try:
        r = requests.get(url, timeout=60)
        root = ET.fromstring(r.content)
        
        # 1. On identifie d'abord les IDs de chaînes qui nous intéressent
        target_ids = set()
        for channel in root.findall('channel'):
            ch_id = channel.get('id')
            # On vérifie si un de nos mots-clés est dans les display-name
            names = [dn.text.upper() for dn in channel.findall('display-name') if dn.text]
            if any(any(kw.upper() in name for kw in KEYWORDS_TO_KEEP) for name in names):
                target_ids.add(ch_id)
        
        print(f"Chaînes identifiées : {len(target_ids)}")

        # 2. On extrait les programmes pour ces IDs
        filtered_data = []
        for prog in root.findall('programme'):
            ch_id = prog.get('channel')
            if ch_id in target_ids:
                title = prog.find('title').text if prog.find('title') is not None else "Match"
                filtered_data.append({
                    "ch": ch_id, # Garde l'ID technique pour le mapping
                    "start": prog.get('start'),
                    "title": title
                })
        
        print(f"Programmes trouvés : {len(filtered_data)}")
        with open('filtered_epg.json', 'w', encoding='utf-8') as f:
            json.dump(filtered_data, f, ensure_ascii=False)
            
    except Exception as e:
        print(f"Erreur : {e}")

if __name__ == "__main__":
    run()
    
