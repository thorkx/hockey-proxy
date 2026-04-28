import xml.etree.ElementTree as ET
import requests
import json

# Liste exhaustive Canada + Europe
CHANNELS_TO_KEEP = [
    # CANADA
    "RDS.ca", "RDS2.ca", "TSN1.ca", "TSN2.ca", "TSN3.ca", "TSN4.ca", "TSN5.ca",
    "SN_East.ca", "SN_Ontario.ca", "SN_One.ca", "SN_360.ca",
    "TVASports.ca", "TVASports2.ca", "OneSoccer.ca",
    # FRANCE
    "CanalPlus.fr", "CanalPlusSport.fr", "CanalPlusFoot.fr", "CanalPlusSport360.fr",
    "BeINSports1.fr", "BeINSports2.fr", "BeINSports3.fr", "DAZN1.fr", "DAZN2.fr"
]

def run():
    url = "https://raw.githubusercontent.com/acidjesuz/EPGTalk/master/guide.xml"
    print("Téléchargement de l'EPG source...")
    
    try:
        r = requests.get(url, timeout=60)
        if r.status_code != 200:
            print("Erreur de téléchargement")
            return

        print("Parsing XML (cela peut prendre une minute)...")
        root = ET.fromstring(r.content)
        
        filtered_data = []
        for prog in root.findall('programme'):
            ch_id = prog.get('channel')
            if ch_id in CHANNELS_TO_KEEP:
                filtered_data.append({
                    "ch": ch_id,
                    "start": prog.get('start'),
                    "stop": prog.get('stop'),
                    "title": prog.find('title').text if prog.find('title') is not None else "Match"
                })
        
        print(f"Succès : {len(filtered_data)} programmes extraits.")
        with open('filtered_epg.json', 'w', encoding='utf-8') as f:
            json.dump(filtered_data, f, ensure_ascii=False)
            
    except Exception as e:
        print(f"Erreur : {e}")

if __name__ == "__main__":
    run()
    
