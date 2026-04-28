import xml.etree.ElementTree as ET
import requests
import json
from datetime import datetime

CHANNELS_TO_KEEP = [
    # --- CANADA ---
    "RDS.ca", "RDS2.ca", "TSN1.ca", "TSN2.ca", "TSN3.ca", "TSN4.ca", "TSN5.ca",
    "SN_East.ca", "SN_Ontario.ca", "SN_One.ca", "SN_360.ca",
    "TVASports.ca", "TVASports2.ca", "OneSoccer.ca",
    
    # --- FRANCE (Foot Européen) ---
    "CanalPlus.fr", "CanalPlusSport.fr", "CanalPlusFoot.fr", "CanalPlusSport360.fr",
    "BeINSports1.fr", "BeINSports2.fr", "BeINSports3.fr",
    "DAZN1.fr", "DAZN2.fr",
    
    # --- UK (Optionnel - Pour feeds anglais) ---
    "SkySportsMainEvent.uk", "SkySportsFootball.uk", "SkySportsPL.uk",
    "TNT_Sports_1.uk", "TNT_Sports_2.uk"
]

def run():
    url = "https://raw.githubusercontent.com/acidjesuz/EPGTalk/master/guide.xml"
    r = requests.get(url)
    root = ET.fromstring(r.content)
    
    results = []
    for prog in root.findall('programme'):
        if prog.get('channel') in CHANNELS_TO_KEEP:
            results.append({
                "ch": prog.get('channel'),
                "start": prog.get('start'),
                "title": prog.find('title').text
            })
            
    with open('filtered_epg.json', 'w') as f:
        json.dump(results, f)

if __name__ == "__main__":
    run()
  
