from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
import requests
import json
import re
import gzip
import xml.etree.ElementTree as ET
from pathlib import Path

FILTERED_EPG_PATH = Path(__file__).resolve().parent / "filtered_epg.json"
SCHEDULE_PATH = Path(__file__).resolve().parent / "schedule.json"
BIBLE_URL = "https://raw.githubusercontent.com/thorkx/hockey-proxy/main/filtered_epg.json"

EPG_SOURCE = {
    "CA": "https://epgshare01.online/epgshare01/epg_ripper_CA2.xml.gz",
    "USA": "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
    "UK": "https://epgshare01.online/epgshare01/epg_ripper_UK1.xml.gz",
    "FR": "https://epgshare01.online/epgshare01/epg_ripper_FR1.xml.gz"
}

PRIORITY_CONFIG = {
    "LEAGUES": {
        "nhl": 800, "nba": 250, "wnba": 250, "uefa.champions": 375,
        "eng.1": 350, "fra.1": 350, "ita.1": 150, "esp.1": 150,
        "uefa.europa": 350, "mlb": 250, "usa.1": 450,
        "concacaf.nations": 600, "concacaf.champions": 500,
        "f1": 400
    },
    "TEAMS": {
        "CANADIENS": 3500,
        "COLORADO AVALANCHE": 1500,
        "WREXHAM AFC": 1500,
        "WREXHAM": 1200,
        "MANCHESTER CITY": 1500,
        "PARIS SAINT-GERMAIN": 1500,
        "TORONTO BLUE JAYS": 1500,
        "TORONTO RAPTORS": 1500,
        "CF MONTREAL": 1000,
        "SUPRA DU QUEBEC": 1500,
        "SUPRA": 1500,
        "ROSES DE MONTREAL": 1200,
        "VICTOIRE DE MONTREAL": 1200,
        "CANMNT": 2000,
        "CANWNT": 2000
    },
    "CHANNELS": {
        "BONUS_HOCKEY_CANADA": 1200,
        "BONUS_ENGLISH_PREMIUM": 500,
        "BONUS_FRENCH": 300,
        "PENALTY_TVA": -150
    }
}

CANADA_HOCKEY_IDS = [
    "Réseau.des.Sports.(RDS).HD.ca2", "RDS2.HD.ca2",
    "Réseau.des.Sports.Info.HD.ca2", "TVA.Sports.HD.ca2",
    "TVA.Sports.2.HD.ca2", "TSN.4K.ca2", "TSN2", "TSN3",
    "TSN4", "TSN5", "Sportsnet.4K.ca2", "Sportsnet.One.HD.ca2",
    "Sportsnet.360.HD.ca2", "Sportsnet.East.HD.ca2", "Sportsnet.West.HD.ca2",
    "One.Soccer.ca2", "Sportsnet.World.HD.ca2"
]


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
    "IonTV.us": {"name": "Ion TV", "id": "16826", "lang": "EN", "country": "USA"},
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

STREAM_BASE = "http://omegatv.live:80/tDcJnv4jMM/2khBtbUZuV"


SPORT_LOGOS = {
    'nhl': '🏒',
    'nba': '🏀',
    'wnba': '🏀',
    'mlb': '⚾',
    'f1': '🏎️',
    'soccer': '⚽',
    'eng.1': '⚽',
    'fra.1': '⚽',
    'ita.1': '⚽',
    'esp.1': '⚽',
    'usa.1': '⚽',
    'uefa.champions': '⚽',
    'concacaf.nations': '⚽'
}

def get_sport_icon(league):
    if not league:
        return ""

    l = league.lower()

    for key, icon in SPORT_LOGOS.items():
        if key in l:
            return icon + " "

    return ""
    

def load_filtered_epg():
    if FILTERED_EPG_PATH.exists():
        try:
            return json.loads(FILTERED_EPG_PATH.read_text(encoding="utf-8"))
        except:
            pass

    try:
        r = requests.get(BIBLE_URL, timeout=10)
        return r.json()
    except:
        return []


def clean_name(t):
    if not t:
        return ""
    t = t.upper()
    t = re.sub(r'HOCKEY|LNH|NBA|SOCCER|FOOTBALL| AT | VS |CONTRE', ' ', t)
    t = re.sub(r'[ÉÈÊË]', 'E', t)
    t = re.sub(r'[ÀÂÄ]', 'A', t)
    return re.sub(r'[^\w\s]', ' ', t)


def parse_espn_time(ev_date_str):
    return datetime.fromisoformat(ev_date_str.replace('Z', '+00:00')).astimezone(timezone.utc).replace(tzinfo=None)


def parse_program_start(prog_start_str):
    # On capture 14 chiffres pour inclure les secondes (YYYYMMDDHHMMSS)
    raw_start = re.sub(r'\D', '', prog_start_str)[:14]
    # On crée l'objet et on lui dit immédiatement qu'il est en UTC
    p_start = datetime.strptime(raw_start, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    
    tz_match = re.search(r'([+-]\d{4})$', prog_start_str.strip())
    if tz_match:
        offset = tz_match.group(1)
        sign = 1 if offset[0] == '+' else -1
        hours = int(offset[1:3])
        minutes = int(offset[3:5])
        # Le calcul se fait maintenant sur des objets "aware", donc sans erreur
        p_start = p_start - sign * timedelta(hours=hours, minutes=minutes)
    
    # On retire le tzinfo à la fin pour que le reste de ton bot (qui attend du naïf) ne plante pas
    return p_start.replace(tzinfo=None)


def build_search_text(prog):
    return (
        clean_name(prog.get('title', '')) + ' ' +
        clean_name(prog.get('sub-title', '')) + ' ' +
        clean_name(prog.get('desc', '')) + ' ' +
        clean_name(prog.get('category', ''))
    )


def token_matches_event(token, source_tokens):
    if token in source_tokens:
        return True
    if len(token) < 5:
        return False
    prefix = token[:5]
    for source_token in source_tokens:
        if len(source_token) < 5:
            continue
        if source_token.startswith(prefix) or token.startswith(source_token[:5]):
            return True
    return False


def parse_iso_utc(time_str):
    # Utilise la méthode robuste pour garantir que l'ISO est converti en vrai UTC
    return datetime.fromisoformat(time_str.replace('Z', '+00:00')).astimezone(timezone.utc).replace(tzinfo=None)


def find_matching_bible_records(title, bible, target_time):
    event_terms = prepare_team_keywords(title)
    if not event_terms:
        event_terms = [token for token in clean_name(title).split() if len(token) > 3]
    matches = []

    for prog in bible:
        try:
            prog_start = parse_program_start(prog['start'])
        except Exception:
            continue

        if abs((target_time - prog_start).total_seconds()) > 5400:
            continue

        source_tokens = [t for t in build_search_text(prog).split() if t]
        match_count = sum(1 for term in event_terms if token_matches_event(term, source_tokens))
        if len(event_terms) >= 2 and match_count < 2:
            continue
        if match_count == 0:
            continue

        matches.append({'program': prog, 'start': prog_start, 'match_score': match_count})

    return matches


def verify_schedule(schedule, bible):
    invalid = []
    total = 0

    for channel, events in schedule.get('channels', {}).items():
        for item in events:
            total += 1
            try:
                schedule_start = parse_iso_utc(item['start'])
            except Exception:
                invalid.append((channel, item, []))
                continue

            matches = find_matching_bible_records(item['title'], bible, schedule_start)
            same_channel_matches = [m for m in matches if m['program'].get('ch') == item['ch_key']]
            if same_channel_matches:
                continue

            # allow generic NHL or F1 channel matches for schedule verification
            event_upper = item['title'].upper()
            event_terms = prepare_team_keywords(item['title'])
            for prog in bible:
                if prog.get('ch') != item['ch_key']:
                    continue
                try:
                    prog_start = parse_program_start(prog['start'])
                except Exception:
                    continue
                if abs((schedule_start - prog_start).total_seconds()) > 5400:
                    continue
                source_tokens = [t for t in build_search_text(prog).split() if t]
                match_count = sum(1 for term in event_terms if token_matches_event(term, source_tokens))
                if match_count > 0:
                    same_channel_matches.append({'program': prog, 'match_score': match_count})
                    break
                if ' AT ' in event_upper and is_generic_league_program(prog, 'nhl'):
                    same_channel_matches.append({'program': prog, 'match_score': 1})
                    break
                if any(term in event_upper for term in ['F1', 'GRAND PRIX', 'QUALI', 'PRACTICE', 'RACE', 'SPRINT']) and is_generic_league_program(prog, 'f1'):
                    same_channel_matches.append({'program': prog, 'match_score': 1})
                    break

            if same_channel_matches:
                continue

            invalid.append((channel, item, matches))

    if not invalid:
        print(f'Verification OK: {total} événements correspondants trouvés dans l’EPG source.')
        return

    print(f'Verification: {len(invalid)}/{total} événements sans match exact sur la chaîne attribuée.')
    for channel, item, matches in invalid:
        print(f'  - Slot {channel}: {item["title"]} @{item["start"]} -> {item["ch_key"]}')
        if matches:
            other_channels = sorted({m['program'].get('ch') for m in matches})
            print(f'      correspondances trouvées sur d’autres chaînes: {", ".join(other_channels)}')
        else:
            print('      aucune correspondance trouvée dans filtered_epg.json')


def prepare_team_keywords(ev_name):
    raw_name = ev_name.upper()
    split_parts = re.split(r'\b(?:AT|VS|CONTRE)\b', raw_name)
    tokens = []
    for part in split_parts:
        for token in clean_name(part).split():
            if len(token) <= 3 or token in ['CF', 'FC', 'LIVE', 'MATCH', 'GAME']:
                continue
            tokens.append(token)

    if not tokens:
        tokens = [w for w in clean_name(ev_name).split() if len(w) > 3 and w not in ['CF', 'FC', 'LIVE', 'MATCH', 'GAME']]

    if 'CANADIENS' in raw_name and 'CANADIENS' not in tokens:
        tokens.append('CANADIENS')
    return tokens


def is_generic_league_program(prog, lg):
    raw_text = ' '.join([
        prog.get('title', ''), prog.get('sub-title', ''), prog.get('desc', ''), prog.get('category', '')
    ]).upper()
    if lg == 'nhl':
        return 'HOCKEY' in raw_text and ('NHL' in raw_text or 'LNH' in raw_text)
    if lg == 'f1':
        return any(term in raw_text for term in ['F1', 'FORMULA', 'GRAND PRIX', 'RACE', 'AUTO', 'MOTOR', 'CIRCUIT'])
    return False


def find_all_matches_in_bible(ev_name, bible_data, ev_date_str, lg=None):
    candidates = []
    try:
        ev_time = parse_espn_time(ev_date_str)
        event_terms = prepare_team_keywords(ev_name)
        if not event_terms:
            event_terms = [t for t in clean_name(ev_name).split() if len(t) > 3]

        for prog in bible_data:
            try:
                p_start = parse_program_start(prog['start'])
            except Exception:
                continue

            time_diff = abs((ev_time - p_start).total_seconds())
            if time_diff > 5400:
                continue

            source_tokens = [t for t in build_search_text(prog).split() if t]
            match_count = sum(1 for term in event_terms if token_matches_event(term, source_tokens))
            generic_match = False
            if match_count == 0:
                if lg in ['nhl', 'f1'] and is_generic_league_program(prog, lg) and time_diff <= 3600:
                    match_count = 1
                    generic_match = True
                else:
                    continue
            if len(event_terms) >= 2 and match_count < 2 and not generic_match:
                continue

            # Reject matches where source program is clearly a different sport
            source_text = ' '.join(source_tokens).upper()
            if any(term in source_text for term in ['F1', 'FORMULA', 'GRAND PRIX', 'RACE', 'AUTO', 'MOTOR', 'CIRCUIT']):
                # Check if event title suggests F1/motorsport
                event_upper = ev_name.upper()
                if not any(term in event_upper for term in ['F1', 'FORMULA', 'GRAND PRIX', 'RACE', 'AUTO', 'MOTOR']):
                    continue

            candidates.append({
                'ch_key': prog.get('ch'),
                'match_score': match_count,
                'time_diff': time_diff
            })
    except:
        pass
    return candidates


def fetch_espn(url):
    try:
        return requests.get(url, timeout=5).json()
    except:
        return {}


def is_rds_channel(ch_key):
    return ch_key in {
        "Réseau.des.Sports.(RDS).HD.ca2",
        "RDS2.HD.ca2",
        "Réseau.des.Sports.Info.HD.ca2"
    }


def is_tva_channel(ch_key):
    return ch_key and ('TVA' in str(ch_key).upper() or '184811' in str(ch_key))


def is_sky_f1_channel(ch_key):
    return ch_key == 'SkySp.F1.HD.uk'


def channel_language(ch_key):
    info = CH_DATABASE.get(ch_key, {})
    return info.get('lang', '').upper()


def fetch_f1_openf1():
    try:
        now = datetime.now(timezone.utc)
        f1_url = f"https://api.openf1.org/v1/sessions?year={now.year}"
        r = requests.get(f1_url, timeout=5)
        if r.status_code != 200: return []
        return [{
            'id': f"f1-{s['session_key']}",
            'name': f"F1 {s['location']} - {s['session_name']}".upper(),
            'date': s['date_start'],
            'league': 'f1'
        } for s in r.json()]
    except: return []


def f1_event_type(name):
    upper_name = name.upper()
    if any(term in upper_name for term in ['PRACTICE', 'FP1', 'FP2', 'FP3', 'FREE PRACTICE']):
        return 'practice'
    if any(term in upper_name for term in ['QUALI', 'QUALIFY', 'QUALIFICATION', 'Q1', 'Q2', 'Q3']):
        return 'qualifying'
    if any(term in upper_name for term in ['GRAND PRIX', 'GP', 'SPRINT', 'RACE']):
        return 'race'
    return None


def calculate_score(name, ch_key, lg):
    score = PRIORITY_CONFIG['LEAGUES'].get(lg, 100)
    for team, bonus in PRIORITY_CONFIG['TEAMS'].items():
        if team in name:
            score += bonus

    info = CH_DATABASE.get(ch_key, {})
    lang = channel_language(ch_key)
    is_fr = lang == 'FR'
    is_en = lang == 'EN'

    if lg == 'nhl':
        if is_rds_channel(ch_key):
            score += 300
        elif is_en:
            score += 150
        elif is_fr:
            score += 75
        if is_tva_channel(ch_key):
            score -= 100
        if ch_key in CANADA_HOCKEY_IDS:
            score += PRIORITY_CONFIG['CHANNELS']['BONUS_HOCKEY_CANADA']

    if 'CANADIENS' in name:
        if is_rds_channel(ch_key) or is_fr:
            score += 300
        elif is_en:
            score += 100

    soccer_leagues = ['soccer', 'eng.1', 'fra.1', 'ita.1', 'esp.1', 'uefa', 'concacaf']
    if any(x in lg for x in soccer_leagues):
        if is_fr:
            score += 200
        elif is_en:
            score += 100
        if is_tva_channel(ch_key):
            score -= 100

    if lg == 'mlb':
        if is_fr:
            score += 150
        elif is_en:
            score += 100

    if lg == 'nba':
        if is_fr:
            score += 150
        elif is_en:
            score += 100

    if lg == 'f1':
        f1_type = f1_event_type(name)
        if f1_type == 'race':
            score += 2000
        elif f1_type == 'qualifying':
            score += 150
            if is_sky_f1_channel(ch_key):
                score += 125
            elif is_en:
                score += 125
            elif is_fr:
                score += 75
        elif f1_type == 'practice':
            score += 10
            if is_sky_f1_channel(ch_key):
                score += 25
            elif is_en:
                score += 10
            elif is_fr:
                score += 5

    if is_tva_channel(ch_key) and lg != 'nhl':
        score -= 50

    return score

def generate_schedule(days=2):
    bible = load_filtered_epg()
    now = datetime.now(timezone.utc)
    leagues = [
        ('hockey','nhl'), ('basketball','nba'), ('baseball','mlb'),
        ('soccer','eng.1'), ('soccer','fra.1'), ('soccer','ita.1'),
        ('soccer','esp.1'), ('soccer','usa.1'), ('soccer','uefa.champions'),
        ('soccer','concacaf.nations'), ('racing','f1')
    ]
    
    events_to_process = []
    
    # --- SOURCE 1: OPENF1 (Précision pour la F1) ---
    try:
        f1_url = f"https://api.openf1.org/v1/sessions?year={now.year}"
        f1_resp = requests.get(f1_url, timeout=5).json()
        for s in f1_resp:
            events_to_process.append({
                'id': f"f1-{s['session_key']}",
                'name': f"F1 {s['location']} - {s['session_name']}".upper(),
                'date': s['date_start'],
                'lg': 'f1'
            })
    except:
        pass

    # --- SOURCE 2: ESPN ---
    urls = []
    for day in range(days):
        ds = (now + timedelta(days=day)).strftime('%Y%m%d')
        for sp, lg in leagues:
            urls.append((f'https://site.api.espn.com/apis/site/v2/sports/{sp}/{lg}/scoreboard?dates={ds}', lg))

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(fetch_espn, url): lg for url, lg in urls}
        for future in futures:
            lg = futures[future]
            for ev in future.result().get('events', []):
                events_to_process.append({
                    'id': ev.get('id') or f"{ev.get('name')}|{ev.get('date')}",
                    'name': ev['name'].upper(),
                    'date': ev['date'],
                    'lg': lg
                })

    # --- TRAITEMENT DES ÉVÉNEMENTS ---
    events = []
    seen_events = set()
    
    for item in events_to_process:
        event_id = item['id']
        if event_id in seen_events:
            continue
        seen_events.add(event_id)

        name = item['name']
        lg = item['lg']
        
        matches = find_all_matches_in_bible(name, bible, item['date'], lg)
        if not matches:
            continue
            
        hits = []
        for match in matches:
            hits.append({
                'ch_key': match['ch_key'],
                'match_score': match['match_score'],
                'score': calculate_score(name, match['ch_key'], lg),
                'time_diff': match['time_diff']
            })
            
        hits.sort(key=lambda x: (x['match_score'], x['score'], -x['time_diff']), reverse=True)
        
        if lg == 'f1' and f1_event_type(name) == 'race':
            sky_hit = next((h for h in hits if is_sky_f1_channel(h['ch_key'])), None)
            rds_hit = next((h for h in hits if is_rds_channel(h['ch_key'])), None)
            if rds_hit:
                events.append({'title': get_sport_icon(lg) + name, 'ch_key': rds_hit['ch_key'], 'score': rds_hit['score'], 'start': start, 'stop': start + timedelta(hours=3)})
            if sky_hit:
                events.append({'title': get_sport_icon(lg) + name, 'ch_key': sky_hit['ch_key'], 'score': sky_hit['score'], 'start': start, 'stop': start + timedelta(hours=3)})
                    
        elif 'CANADIENS' in name:
            start = parse_espn_time(item['date'])
            english_hit = next((h for h in hits if channel_language(h['ch_key']) == 'EN'), None)
            french_hit = next((h for h in hits if channel_language(h['ch_key']) == 'FR'), None)
            
            if french_hit:
                events.append({'title': get_sport_icon(lg) + name, 'ch_key': french_hit['ch_key'], 'score': french_hit['score'], 'start': start, 'stop': start + timedelta(hours=3)})
            if english_hit and english_hit['ch_key'] != (french_hit or {}).get('ch_key'):
                events.append({'title': get_sport_icon(lg) + name, 'ch_key': english_hit['ch_key'], 'score': english_hit['score'], 'start': start, 'stop': start + timedelta(hours=3)})
            if not french_hit and not english_hit:
                events.append({'title': get_sport_icon(lg) + name, 'ch_key': hits[0]['ch_key'], 'score': hits[0]['score'], 'start': start, 'stop': start + timedelta(hours=3)})
        else:
            start = parse_espn_time(item['date'])
            events.append({'title': get_sport_icon(lg) + name, 'ch_key': hits[0]['ch_key'], 'score': hits[0]['score'], 'start': start, 'stop': start + timedelta(hours=3)})

    # --- PACKING DANS LES CANAUX (1-5) ---
    events.sort(key=lambda e: e['score'], reverse=True)
    chans = {str(i): [] for i in range(1, 6)}
    
    for event in events:
        display_start = event['start'] - timedelta(minutes=30)
        for slot in range(1, 6):
            channel_events = chans[str(slot)]
            can_fit = True
            final_start = display_start
            
            for existing in channel_events:
                existing_start = existing['display_start_dt']
                existing_stop = existing['stop_dt']
                if not (event['stop'] <= existing_start or display_start >= existing_stop):
                    if existing_stop <= event['start']:
                        final_start = existing_stop
                    else:
                        can_fit = False
                        break
            
            if can_fit:
                full_title = event['title']
                channel_events.append({
                    'title': full_title,
                    'ch_key': event['ch_key'],
                    'score': event['score'],
                    'display_start': final_start.strftime('%Y-%m-%dT%H:%M:%SZ'),
                    'stop': event['stop'].strftime('%Y-%m-%dT%H:%M:%SZ'),
                    'start': event['start'].strftime('%Y-%m-%dT%H:%M:%SZ'),
                    'display_start_dt': final_start,
                    'stop_dt': event['stop']
                })
                break

    # Nettoyage des objets datetime avant retour
    for channel_events in chans.values():
        for item in channel_events:
            item.pop('display_start_dt', None)
            item.pop('stop_dt', None)

    return {
        'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'channels': chans
    }
    


def save_schedule(schedule):
    try:
        SCHEDULE_PATH.write_text(json.dumps(schedule, indent=2, ensure_ascii=False), encoding='utf-8')
    except Exception as exc:
        print(f'Erreur écriture schedule: {exc}')


def  generate_filtered_epg():
    now = datetime.now(timezone.utc)
    min_time = now - timedelta(hours=8)
    max_time = now + timedelta(days=3)
    results = []
    for country, url in EPG_SOURCE.items():
        with gzip.open(requests.get(url, stream=True).raw) as f:
            tree = ET.parse(f)
            root = tree.getroot()
            for prog in root.findall('.//programme'):
                try:
                    start = parse_program_start(prog.get('start'))
                    if not (min_time <= start <= max_time):
                        continue
                    ch = prog.get('channel')
                    if ch not in CH_DATABASE:
                        continue
                    title = prog.findtext('title') or ''
                    sub_title = prog.findtext('sub-title') or ''
                    desc = prog.findtext('desc') or ''
                    category = prog.findtext('category') or ''
                    results.append({'ch': ch, 'start': start.isoformat(), 'title': title, 'sub-title': sub_title, 'desc': desc, 'category': category})
                except Exception:
                    continue
    with open(FILTERED_EPG_PATH, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)


def main():
    generate_filtered_epg()
    bible = load_filtered_epg()
    schedule = generate_schedule(days=2)
    verify_schedule(schedule, bible)
    save_schedule(schedule)
    print(f'Schedule généré: {SCHEDULE_PATH} ({len(schedule.get("channels", {}))} canaux)')


if __name__ == '__main__':
    main()
    
