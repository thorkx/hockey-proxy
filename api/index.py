from http.server import BaseHTTPRequestHandler
import requests
import json
import re
from datetime import datetime, timedelta

JSON_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

MAP = {
    "I123.15676.schedulesdirect.org": "184813", # RDS 1
    "I124.39080.schedulesdirect.org": "184814", # RDS 2
    "I111.15670.schedulesdirect.org": "184816", # TSN 1
    "I154.58314.schedulesdirect.org": "184821", # TVA Sports
    "I1000.49609.schedulesdirect.org": "176800",# Sky Main Event
    "I1001.104327.schedulesdirect.org": "176801",# Sky Football
    "I446.52300.schedulesdirect.org": "157280",  # Sky Mexico
    "I428.49882.gracenote.com": "71518",        # Sportsnet East
    "I432.49886.gracenote.com": "71522"         # Sportsnet One
}

PRIORITIES = ["CANADIENS", "MONTRÉAL", "PSG", "CITY", "F1", "EFL", "LIVE"]

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        events = []
        try:
            # On force le chargement du JSON sans vérifier le cache SSL trop sévèrement
            r = requests.get(JSON_URL, timeout=10, verify=True)
            data = re.search(r'\[.*\]', r.text, re.DOTALL)
            if data:
                events = json.loads(data.group(0))
        except:
            pass

        # Matching des événements
        matches = []
        for e in events:
            ch_id = str(e.get('ch', '')).strip()
            if ch_id in MAP:
                title = e.get('title', '').upper()
                score = next((i for i, t in enumerate(PRIORITIES) if t in title), 99)
                matches.append({
                    'title': e.get('title'),
                    'sid': MAP[ch_id],
                    'start': e.get('start', '').replace(" ", "").replace("+0000", "")[:14],
                    'score': score
                })
        
        matches.sort(key=lambda x: x['score'])

        # SORTIE XML
        if "type=xml" in self.path:
            self.send_response(200)
            self.send_header('Content-type', 'application/xml; charset=utf-8')
            self.end_headers()
            
            xml = '<?xml version="1.0" encoding="UTF-8"?>\n<tv>\n'
            for i in range(1, 6):
                xml += f'  <channel id="CHOIX.{i}"><display-name>CHOIX {i}</display-name></channel>\n'
            
            # Si pas de matchs trouvés, on remet le "Match Test" pour pas que ce soit vide
            display_list = matches if matches else [{'title': 'Aucun match trouvé', 'start': '20260428200000'}] * 5

            for i, m in enumerate(display_list[:5]):
                ch_num = i + 1
                t_start = m['start'].ljust(14, '0')
                # On met une durée de 4h pour que ça reste affiché dans le guide
                dt_stop = datetime.strptime(t_start, "%Y%m%d%H%M%S") + timedelta(hours=4)
                stop = dt_stop.strftime("%Y%m%d%H%M%S")
                
                xml += f'  <programme start="{t_start} +0000" stop="{stop} +0000" channel="CHOIX.{ch_num}">\n'
                xml += f'    <title lang="fr">{m["title"]}</title>\n'
                xml += f'  </programme>\n'
            xml += '</tv>'
            self.wfile.write(xml.encode('utf-8'))

        # SORTIE M3U
        else:
            self.send_response(200)
            self.send_header('Content-type', 'audio/x-mpegurl')
            self.end_headers()
            host = self.headers.get('Host')
            playlist = f'#EXTM3U x-tvg-url="https://{host}/api?type=xml"\n'
            for i in range(1, 6):
                if (i-1) < len(matches):
                    m = matches[i-1]
                    playlist += f'#EXTINF:-1 tvg-id="CHOIX.{i}", CHOIX {i} : {m["title"]}\n'
                    playlist += f'{STREAM_BASE}/{m["sid"]}\n'
                else:
                    playlist += f'#EXTINF:-1 tvg-id="CHOIX.{i}", CHOIX {i} (Vide)\n'
                    playlist += f'http://0.0.0.0\n'
            self.wfile.write(playlist.encode('utf-8'))
            
