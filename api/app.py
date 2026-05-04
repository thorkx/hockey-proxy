import os
from flask import Flask, request, Response, redirect
from pathlib import Path
import json
import html
from datetime import datetime, timedelta, timezone

GLOBAL_DATA = {'chans': None, 'last_update': None}
ROOT_DIR = Path(__file__).resolve().parent
# Note: J'ai retiré un .parent pour que ça cherche dans le dossier du script sur Render
SCHEDULE_PATH = ROOT_DIR / "schedule.json"
FALLBACK_SCHEDULE_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/schedule.json"
STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV/"

CH_DATABASE = {
    "Réseau.des.Sports.(RDS).HD.ca2": {"name": "RDS", "id": "184813", "lang": "FR", "country": "CA"},
    "RDS2.HD.ca2": {"name": "RDS 2", "id": "184814", "lang": "FR", "country": "CA"},
    "Réseau.des.Sports.Info.HD.ca2": {"name": "RDS Info", "id": "184815", "lang": "FR", "country": "CA"},
    "TVA.Sports.HD.ca2": {"name": "TVA Sports", "id": "184811", "lang": "FR", "country": "CA"},
    "TVA.Sports.2.HD.ca2": {"name": "TVA Sports 2", "id": "184812", "lang": "EN", "country": "CA"},
    "Sportsnet.4K.ca2": {"name": "Sportsnet 4K", "id": "157674", "lang": "EN", "country": "CA"},
    "Sportsnet.One.HD.ca2": {"name": "SN One", "id": "157675", "lang": "EN", "country": "CA"},
    "Sportsnet.360.HD.ca2": {"name": "SN 360", "id": "71517", "lang": "EN", "country": "CA"},
    "Sportsnet.East.HD.ca2": {"name": "SN East", "id": "71518", "lang": "EN", "country": "CA"},
    "Sportsnet.West.HD.ca2": {"name": "SN West", "id": "71521", "lang": "EN", "country": "CA"},
    "Sportsnet.(Pacific).HD.ca2": {"name": "SN Pacific", "id": "71520", "lang": "EN", "country": "CA"},
    "TSN.4K.ca2": {"name": "TSN 1", "id": "71234", "lang": "EN", "country": "CA"},
    "TSN.2.ca2": {"name": "TSN 2", "id": "71235", "lang": "EN", "country": "CA"},
    "TSN.3.ca2": {"name": "TSN 3", "id": "71236", "lang": "EN","country":" CA"},
    "TSN.4.ca2": {"name": "TSN 4", "id": "71237", "lang":"EN", "country": "CA"},
    "TSN.5.ca2": {"name": "TSN 5", "id": "71238", "lang":"EN", "country": "CA"},
    "One.Soccer.ca2": {"name": "OneSoccer", "id": "19320", "lang": "EN", "country": "CA"},
    "Sportsnet.World.HD.ca2": {"name": "SN World", "id": "71526", "lang": "EN", "country": "CA"},
    "SkySp.F1.HD.uk": {"name": "Sky F1", "id": "74316", "lang": "EN", "country": "UK"},
    "SkySp.PL.HD.uk": {"name": "Sky PL", "id": "74322", "lang": "EN", "country": "UK"},
    "TNT.Sports.1.HD.uk": {"name": "TNT Sports 1", "id": "74357", "lang": "EN", "country": "UK"},
    "TNT.Sports.2.HD.uk": {"name": "TNT Sports 2", "id": "74360", "lang": "EN", "country": "UK"},
    "TNT.Sports.3.HD.uk": {"name": "TNT Sports 3", "id": "74363", "lang": "EN", "country": "UK"},
    "TNT.Sports.4.HD.uk": {"name": "TNT Sports 4", "id": "75365", "lang": "EN", "country": "UK"},
    "ESPN.HD.us2": {"name": "ESPN", "id": "18345", "lang": "EN", "country": "USA"},
    "ESPN2.HD.us2": {"name": "ESPN2", "id": "18346", "lang": "EN", "country": "USA"},
    "ESPN.Deportes.HD.us2": {"name": "ESPN Deportes", "id": "18356", "lang": "ES", "country": "USA"},
    "FuboSportsNetwork.us2": {"name": "FuboSportsNetwork", "id": "16810", "lang": "EN", "country": "US"},
    "GolazoSports.us2": {"name": "GolazoSports", "id": "18333", "lang": "EN", "country": "US"},
    "beIn.Sports.USA.HD.us2": {"name": "beIN SPORTS USA", "id": "18312", "lang": "EN", "country": "USA"},
    "beIn.Sports.Xtra.us2": {"name": "beIN SPORTS Xtra", "id": "19489", "lang": "EN", "country": "USA"},
    "CBS.Sports.Network.HD.us2": {"name": "CBS Sports Network", "id": "18335", "lang": "EN", "country": "USA"},
    "Fox.Sports.1.HD.us2": {"name": "Fox Sports 1", "id": "18242", "lang": "EN", "country": "USA"},
    "Fox.Sports.2.HD.us2": {"name": "Fox Sports 2", "id": "18366", "lang": "EN", "country":"USA"},
    "Fox.Soccer.Plus.HD.us2": {"name": "Fox Soccer Plus", "id":"18364","lang":"EN","country":"USA"},
    "NBC.Sports.4K.us2": {"name": "NBC Sports 4K",	"id":"18431",	"lang":"EN",	"country":"USA"},
    "beIn.SPORTS.1.fr": {"name": "beIN SPORTS 1",	"id":"49895",	"lang":"FR",	"country":"FR"},
    "beIN.SPORTS.2.fr": {"name": "beIN SPORTS 2",	"id":"49896",	"lang":"FR",	"country":"FR"},
    "beIN.SPORTS.3.fr": {"name": "beIN SPORTS 3", "id": '49897', 'lang': 'FR', 'country': 'FR'},
    "beIN.SPORTS.MAX.4.fr": {"name": 'beIN SPORTS MAX 4', 'id': '49903', 'lang': 'VO', 'country': 'FR'},
    "beIN.SPORTS.MAX.5.fr": {"name": "beIN SPORTS MAX 5", "id": "83080", "lang": "VO", "country": "FR"},
    "beIN.SPORTS.MAX.6.fr": {"name": "beIN SPORTS MAX 6", "id": "83081", "lang": "VO", "country": "FR"},
    "beIN.SPORTS.MAX.7.fr": {"name": "beIN SPORTS MAX 7", "id": "83082", "lang": "VO", "country": "FR"},
    "beIN.SPORTS.MAX.8.fr": {"name": "beIN SPORTS MAX 8", "id": "49904", "lang": "VO", "country": "FR"},
    "Canal+.Sport.360.fr": {"name": "Canal+ Sport 360", "id": "83038", "lang": "FR", "country": "FR"},
    "Canal+.fr": {"name": "Canal+", "id": "49943", "lang": "FR", "country": "FR"},
    "Canal+.Sport.fr": {"name": "Canal+ Sport", "id": "49951", "lang": "FR", "country": "FR"},
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
                dt = datetime.fromisoformat(event['display_start'].replace('Z', ''))
                #display_start = datetime.fromisoformat(event['display_start'].replace('Z', '+00:00')).astimezone(timezone.utc).replace(tzinfo=None)
                display_start = dt.replace(tzinfo=None)
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

def get_cached_chans():
    now = datetime.now(timezone.utc)
    # On ne reparse que si les données ont plus de 5 minutes
    if GLOBAL_DATA['chans'] is None or (now - GLOBAL_DATA['last_update']).seconds > 300:
        GLOBAL_DATA['chans'] = parse_schedule()
        GLOBAL_DATA['last_update'] = now
    return GLOBAL_DATA['chans']

app = Flask(__name__)

@app.route('/')
@app.route('/xmltv.xml')
def xml_route():
    # Logique XML de ton handler
    chans = get_caches_chans()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    xml_out = '<?xml version="1.0" encoding="UTF-8"?>\n<tv>'
    for i in range(1, 6):
        xml_out += f'\n<channel id="CHOIX.{i}"><display-name>CHOIX {i}</display-name></channel>'
        cursor = now - timedelta(hours=12)
        for p in sorted(chans[i], key=lambda x: x['display_start']):
            disp_st = p['display_start'].strftime('%Y%m%d%H%M%S') + ' +0000'
            live_en = p['stop'].strftime('%Y%m%d%H%M%S') + ' +0000'
            ch_name = CH_DATABASE.get(p['ch_key'], {}).get('name', 'NA')
            ch_lang = CH_DATABASE.get(p['ch_key'], {}).get('lang', 'NA')
            title = f"{p['title']} | {ch_name} | {ch_lang}"
            if p['display_start'] > cursor:
                xml_out += f'\n<programme start="{cursor.strftime("%Y%m%d%H%M%S")} +0000" stop="{disp_st}" channel="CHOIX.{i}"><title>À venir: {escape_xml(title)}</title></programme>'
            xml_out += f'\n<programme start="{disp_st}" stop="{live_en}" channel="CHOIX.{i}"><title>🔴 LIVE: {escape_xml(title)}</title></programme>'
            cursor = p['stop']
    xml_out += '\n</tv>'
    return Response(xml_out, mimetype='application/xml')


@app.route('/stream/<int:idx>')
def stream_route(idx):
    try:
        chans = parse_schedule()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        
        print(f"DEBUG: Request for index {idx} at {now}")
        
        # On récupère les événements
        events = chans.get(idx) or chans.get(str(idx)) or []
        
        if not events:
            print(f"DEBUG: No events at all for channel {idx}")
            return redirect(f"{STREAM_BASE.rstrip('/')}/184813", code=302)

        sid = None
        next_event = None

        # 1. Recherche d'un match LIVE
        for m in events:
            if m['display_start'] <= now <= m['stop']:
                sid = get_stream_id(m['ch_key'])
                print(f"DEBUG: MATCH LIVE! {m['title']} -> SID: {sid}")
                break
        
        # 2. Si pas de LIVE, on cherche le PROCHAIN match
        if not sid:
            # On trie les événements par heure de début
            future_events = [e for e in events if e['display_start'] > now]
            future_events.sort(key=lambda x: x['display_start'])
            
            if future_events:
                next_event = future_events[0]
                sid = get_stream_id(next_event['ch_key'])
                print(f"DEBUG: NO LIVE. Next event: {next_event['title']} at {next_event['display_start']} -> SID: {sid}")
            else:
                # 3. Vraiment rien à venir ? Backup RDS
                sid = "184813"
                print("DEBUG: No live or future events. Falling back to RDS.")

        final_url = f"{STREAM_BASE.rstrip('/')}/{sid}"
        return redirect(final_url, code=302)

    except Exception as e:
        print(f"DEBUG: Exception : {e}")
        return redirect(f"{STREAM_BASE.rstrip('/')}/184813", code=302)
    

@app.route('/playlist.m3u')
def m3u_route():
    # Logique M3U de ton handler
    host = request.host
    m3u = "#EXTM3U\n"
    for i in range(1, 6):
        m3u += f'#EXTINF:-1 tvg-id="CHOIX.{i}",CHOIX {i}\n'
        m3u += f'https://{host}/stream/{i}\n'
    return Response(m3u, mimetype='text/plain')

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
