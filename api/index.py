from http.server import BaseHTTPRequestHandler
import requests
import json

JSON_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

# Équivalences
MAP = {
    "I123.15676.schedulesdirect.org": "184813",
    "I124.39080.schedulesdirect.org": "184814",
    "I111.15670.schedulesdirect.org": "184816",
    "I154.58314.schedulesdirect.org": "184821",
    "I1000.49609.schedulesdirect.org": "176800",
    "I1001.104327.schedulesdirect.org": "176801",
    "I446.52300.schedulesdirect.org": "157280",
    "I428.49882.gracenote.com": "71518",
    "I432.49886.gracenote.com": "71522"
}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 1. Fetch direct
        events = []
        try:
            r = requests.get(JSON_URL, timeout=10)
            # Si le fichier contient du texte avant le JSON, on nettoie
            raw_content = r.text.strip()
            # On cherche le premier '[' et le dernier ']'
            start_idx = raw_content.find('[')
            end_idx = raw_content.rfind(']') + 1
            
            if start_idx != -1 and end_idx != 0:
                json_str = raw_content[start_idx:end_idx]
                events = json.loads(json_str)
        except Exception as e:
            # Si ça plante, on crée un événement d'erreur pour le voir dans l'EPG
            events = [{"title": f"ERREUR: {str(e)}", "ch": "debug", "start": "20260428000000"}]

        # 2. Construction de la réponse
        if "type=xml" in self.path:
            self.send_response(200)
            self.send_header('Content-type', 'application/xml; charset=utf-8')
            self.end_headers()
            
            xml = '<?xml version="1.0" encoding="UTF-8"?>\n<tv>\n'
            # On crée les 5 canaux
            for i in range(1, 6):
                xml += f'  <channel id="CHOIX.{i}"><display-name>CHOIX {i}</display-name></channel>\n'
            
            # On remplit les programmes
            for i, e in enumerate(events[:5]):
                ch_num = i + 1
                title = e.get('title', 'Sans Titre')
                start = e.get('start', '20260428000000').replace(" ", "")[:14]
                xml += f'  <programme start="{start} +0000" stop="{start} +0000" channel="CHOIX.{ch_num}">\n'
                xml += f'    <title>{title}</title>\n'
                xml += f'    <desc>ID: {e.get("ch")}</desc>\n'
                xml += f'  </programme>\n'
            
            xml += '</tv>'
            self.wfile.write(xml.encode('utf-8'))
        else:
            # M3U Simple
            self.send_response(200)
            self.send_header('Content-type', 'audio/x-mpegurl')
            self.end_headers()
            host = self.headers.get('Host')
            playlist = f'#EXTM3U x-tvg-url="https://{host}/api?type=xml"\n'
            for i in range(1, 6):
                title = events[i-1].get('title', 'Vide') if (i-1) < len(events) else "Vide"
                sid = MAP.get(events[i-1].get('ch'), "184813") if (i-1) < len(events) else "184813"
                playlist += f'#EXTINF:-1 tvg-id="CHOIX.{i}", CHOIX {i} ({title})\n'
                playlist += f'{STREAM_BASE}/{sid}\n'
            self.wfile.write(playlist.encode('utf-8'))
            
