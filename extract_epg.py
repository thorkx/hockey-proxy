import xml.etree.ElementTree as ET
import requests
import json
from io import BytesIO

# Liste des mots-clés pour filtrer les chaînes sportives
KEYWORDS = ["RDS", "TSN", "SPORTSNET", "SN ", "TVA SPORTS", "CANAL+", "BEIN", "DAZN", "SKY SPORTS", "TNT SPORTS"]

def run():
    url = "https://raw.githubusercontent.com/acidjesuz/EPGTalk/master/guide.xml"
    print("--- DÉBUT DE L'EXTRACTION ---")
    
    try:
        print("Téléchargement du guide XML...")
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        
        # On utilise BytesIO pour ne pas saturer la RAM
        xml_data = BytesIO(r.content)
        
        target_ids = {} # Dictionnaire ID: Nom_Lisible
        filtered_data = []

        # PASSAGE 1 : Identifier les IDs des chaînes qui nous intéressent
        print("Identification des chaînes sportives...")
        context = ET.iterparse(xml_data, events=('start', 'end'))
        for event, elem in context:
            if event == 'end' and elem.tag == 'channel':
                ch_id = elem.get('id')
                names = [dn.text for dn in elem.findall('display-name') if dn.text]
                
                # On filtre pour trouver si un de nos mots-clés est présent
                if any(any(kw.upper() in name.upper() for kw in KEYWORDS) for name in names):
                    # LOGIQUE DE SÉLECTION DU NOM :
                    # On évite les noms qui ne sont que des chiffres. 
                    # On prend le nom le plus long parmi ceux qui contiennent des lettres.
                    clean_names = [n for n in names if any(c.isalpha() for c in n)]
                    if clean_names:
                        target_ids[ch_id] = max(clean_names, key=len)
                    else:
                        target_ids[ch_id] = names[0] # Fallback sur le premier si vraiment rien d'autre
                
                elem.clear()
                
        # PASSAGE 2 : Extraire les programmes pour ces chaînes
        xml_data.seek(0) # On rembobine le fichier en mémoire
        print("Filtrage des programmes...")
        context = ET.iterparse(xml_data, events=('start', 'end'))
        for event, elem in context:
            if event == 'end' and elem.tag == 'programme':
                ch_id = elem.get('channel')
                
                if ch_id in target_ids:
                    title_node = elem.find('title')
                    title = title_node.text if title_node is not None else "Événement Sportif"
                    
                    filtered_data.append({
                        "ch": ch_id,
                        "name": target_ids[ch_id], # Ajout du nom lisible (ex: RDS)
                        "start": elem.get('start'),
                        "title": title
                    })
                
                elem.clear() # Nettoyage mémoire

        # SAUVEGARDE
        print(f"Extraction terminée : {len(filtered_data)} programmes conservés.")
        with open('filtered_epg.json', 'w', encoding='utf-8') as f:
            json.dump(filtered_data, f, ensure_ascii=False, indent=2)
        
        print("Fichier 'filtered_epg.json' mis à jour avec succès.")

    except Exception as e:
        print(f"ERREUR CRITIQUE : {e}")

if __name__ == "__main__":
    run()
    
