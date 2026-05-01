import os
from flask import Flask, request, Response, redirect
from pathlib import Path
import json
import html
from datetime import datetime, timedelta, timezone

# --- TON CODE INTACT ---
ROOT_DIR = Path(__file__).resolve().parent
# Note: J'ai retiré un .parent pour que ça cherche dans le dossier du script sur Render
SCHEDULE_PATH = ROOT_DIR / "schedule.json"
FALLBACK_SCHEDULE_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/schedule.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"

CH_DATABASE = {
    "Réseau.des.Sports.(RDS).HD.ca2": {"name": "RDS", "id": "184813", "lang": "FR"},
    "RDS2.HD.ca2": {"name": "RDS 2", "id": "184814", "lang": "FR"},
    "Réseau.des.Sports.Info.HD.ca2": {"name": "RDS Info", "id": "184815", "lang": "FR"},
    "TVA.Sports.HD.ca2": {"name": "TVA Sports", "id": "184811", "lang": "FR"},
    "TVA.Sports.2.HD.ca2": {"name": "TVA Sports 2", "id": "184812", "lang": "EN"},
    "Sportsnet.4K.ca2": {"name": "Sportsnet 4K", "id": "157674", "lang": "EN"},
    "Sportsnet.One.HD.ca2": {"name": "SN One", "id": "157675", "lang": "EN"},
    "Sportsnet.360.HD.ca2": {"name": "SN 360", "id": "71517", "lang": "EN"},
    "Sportsnet.East.HD.ca2": {"name": "SN East", "id": "71518", "lang": "EN"},
    "Sportsnet.West.HD.ca2": {"name": "SN West", "id": "71521", "lang": "EN"},
    "Sportsnet.(Pacific).HD.ca2": {"name": "SN Pacific", "id": "71520", "lang": "EN"},
    "TSN.4K.ca2": {"name": "TSN 1", "id": "71234", "lang": "EN"},
    "TSN.2.ca2": {"name": "TSN 2", "id": "71235", "lang": "EN"},
    "TSN.3.ca2": {"name": "TSN 3", "id": "71236", "lang": "EN"},
    "TSN.4.ca2": {"name": "TSN 4", "id": "71237", "lang": "EN"},
    "TSN.5.ca2": {"name": "TSN 5", "id": "71238", "lang": "EN"},
    "One.Soccer.ca2": {"name": "OneSoccer", "id": "19320", "lang": "EN"},
    "Sportsnet.World.HD.ca2": {"name": "SN World", "id": "71526", "lang": "EN"},
    "SkySp.F1.HD.uk": {"name": "Sky F1", "id": "000000", "lang": "EN"},
    "TNT.Sports.1.HD.uk": {"name": "TNT Sports 1", "id": "TNT.Sports.1.HD.uk", "lang": "EN"},
    "Canal+.Sport.360.fr": {"name": "Canal+ Sport 360", "id": "Canal+.Sport.360.fr", "lang": "FR"},
    "ESPN.Deportes.HD.us2": {"name": "ESPN Deportes", "id": "ESPN.Deportes.HD.us2", "lang": "ES"},
    "Fox.Soccer.Plus.HD.us2": {"name": "Fox Soccer Plus", "id": "Fox.Soccer.Plus.HD.us2", "lang": "EN"},
    "NBC.Sports.4K.us2": {"name": "NBC Sports 4K", "id": "NBC.Sports.4K.us2", "lang": "EN"},
    "beIN.SPORTS.MAX.4.fr": {"name": "beIN SPORTS MAX 4", "id": "beIN.SPORTS.MAX.4.fr", "lang": "FR"},
    "beIN.SPORTS.MAX.8.fr": {"name": "beIN SPORTS MAX 8", "id": "beIN.SPORTS.MAX.8.fr", "lang": "FR"}
}

CACHE = {'schedule': None, 'mtime': None}

def escape_xml(text):
    if not text: return ""
    return html.escape(text).encode('ascii', 'xmlcharrefreplace').decode()

def get_stream_id(ch_key):
    return CH_DATABASE.get(ch_key, {}).get('id', ch_key)

def load_schedule():
    try:
        if SCHEDULE_PATH.exists():
            mtime = SCHEDULE_PATH.stat().st_mtime
            if CACHE['schedule'] is None or CACHE['mtime'] != mtime:
                CACHE['schedule'] = json.loads(SCHEDULE_PATH.read_text(encoding='utf-8'))
                CACHE['mtime'] = mtime
            return CACHE['schedule']
    except Exception: pass
    try:
        import requests
        return requests.get(FALLBACK_SCHEDULE_URL, timeout=5).json()
    except Exception:
        return {"channels": {str(i): [] for i in range(1, 6)}}

def parse_schedule():
    raw = load_schedule()
    chans = {i: [] for i in range(1, 6)}
    for i in range(1, 6):
        for event in raw.get('channels', {}).get(str(i), []):
            try:
                display_start = datetime.fromisoformat(event['display_start'].replace('Z', '+00:00')).astimezone(timezone.utc).replace(tzinfo=None)
                stop = datetime.fromisoformat(event['stop'].replace('Z', '+00:00')).astimezone(timezone.utc).replace(tzinfo=None)
                chans[i].append({
                    'title': event.get('title', ''),
                    'ch_key': event.get('ch_key', ''),
                    'display_start': display_start,
                    'stop': stop,
                    'score': event.get('score', 0)
                })
            except Exception: continue
    return chans

# --- ADAPTATION RENDER (FLASK) ---
app = Flask(__name__)

@app.route('/')
@app.route('/xmltv.xml')
def xml_route():
    # Logique XML de ton handler
    chans = parse_schedule()
    now = datetime.utcnow()
    xml_out = '<?xml version="1.0" encoding="UTF-8"?>\n<tv>'
    for i in range(1, 6):
        xml_out += f'\n<channel id="CHOIX.{i}"><display-name>CHOIX {i}</display-name></channel>'
        cursor = now - timedelta(hours=12)
        for p in sorted(chans[i], key=lambda x: x['display_start']):
            disp_st = p['display_start'].strftime('%Y%m%d%H%M%S') + ' +0000'
            live_en = p['stop'].strftime('%Y%m%d%H%M%S') + ' +0000'
            ch_name = CH_DATABASE.get(p['ch_key'], {}).get('name', 'SOURCE')
            title = f"{p['title']} | {ch_name}"
            if p['display_start'] > cursor:
                xml_out += f'\n<programme start="{cursor.strftime("%Y%m%d%H%M%S")} +0000" stop="{disp_st}" channel="CHOIX.{i}"><title>À venir: {escape_xml(title)}</title></programme>'
            xml_out += f'\n<programme start="{disp_st}" stop="{live_en}" channel="CHOIX.{i}"><title>🔴 LIVE: {escape_xml(title)}</title></programme>'
            cursor = p['stop']
    xml_out += '\n</tv>'
    return Response(xml_out, mimetype='application/xml')

@app.route('/api/stream/<int:idx>')
def stream_route(idx):
    # Logique Redirect de ton handler
    try:
        chans = parse_schedule()
        now = datetime.utcnow()
        sid = "184813"
        for m in chans.get(idx, []):
            if m['display_start'] <= now <= m['stop']:
                sid = get_stream_id(m['ch_key'])
                break
        return redirect(f"{STREAM_BASE}/{sid}", code=302)
    except Exception:
        return redirect(f"{STREAM_BASE}/184813", code=302)

@app.route('/playlist.m3u')
def m3u_route():
    # Logique M3U de ton handler
    host = request.host
    m3u = "#EXTM3U\n"
    for i in range(1, 6):
        m3u += f'#EXTINF:-1 tvg-id="CHOIX.{i}",CHOIX {i}\n'
        m3u += f'https://{host}/api/stream/{i}\n'
    return Response(m3u, mimetype='text/plain')

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
