from http.server import BaseHTTPRequestHandler, HTTPServer
import requests
import json
import re
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher

# [Garder PRIORITY_CONFIG, CANADA_HOCKEY_IDS et CH_DATABASE tels quels]

# ==========================================
#        LOGIQUE DE DÉDUCTION (QUALITÉ)
# ==========================================
def find_best_match_in_bible(ev_name, bible_data, ev_date_str, lg):
    best_hit = None
    max_quality = -999
    
    try:
        ev_time = parse_event_time(ev_date_str)
        teams = prepare_team_keywords(ev_name)
        
        for prog in bible_data:
            p_start = parse_program_start(prog['start'])
            
            # 1. Filtre temporel (Fenêtre de 2h)
            if abs((ev_time - p_start).total_seconds()) > 7200:
                continue
            
            # 2. Score de base par durée (Élimine les "News" de 30 min)
            quality = 0
            p_stop = parse_program_start(prog['stop'])
            duration_min = (p_stop - p_start).total_seconds() / 60
            
            if 110 <= duration_min <= 240: quality += 50 
            elif duration_min < 45: quality -= 80 # Fort malus pour les formats courts
            
            # 3. Matching de texte (Plus rapide que le fuzzy match complet)
            full_text = build_search_text(prog)
            match_count = sum(1 for t in teams if t[:4] in full_text)
            
            if match_count == 0: continue
            quality += (match_count * 40)
            
            # 4. Bonus/Malus de catégorie et titre
            cat = str(prog.get('category', '')).upper()
            title_upper = str(prog.get('title', '')).upper()
            
            if any(kw in cat or kw in title_upper for kw in ['LIVE', 'DIRECT', 'MATCH', 'JEU']): quality += 40
            if any(kw in cat or kw in title_upper for kw in ['TALK', 'NEWS', 'RECAP', 'HIGHLIGHT', '30 IN 30']): quality -= 100

            # On ne garde que le meilleur candidat
            if quality > max_quality:
                max_quality = quality
                best_hit = {"ch": prog['ch'], "quality": quality, "prog_ref": prog, "confidence": (match_count/len(teams) if teams else 0)}
                
    except: pass
    
    # Seuil de rigueur : si la qualité est trop basse, on ignore
    return best_hit if max_quality > 40 else None

# ==========================================
#                SERVEUR HTTP
# ==========================================
CACHE_ORGANIZED = {"chans": {}, "timestamp": None}

class handler(BaseHTTPRequestHandler):
    def get_organized_events(self):
        now = datetime.utcnow()
        if CACHE_ORGANIZED["timestamp"] and (now - CACHE_ORGANIZED["timestamp"]).total_seconds() < 300:
            return CACHE_ORGANIZED["chans"]

        bible = get_bible()
        events, seen = [], set()
        leagues = [("hockey","nhl"), ("basketball","nba"), ("baseball","mlb"), ("soccer","eng.1"), ("soccer","fra.1"), ("soccer","ita.1"), ("soccer","esp.1"), ("soccer","usa.1"), ("soccer","uefa.champions"), ("soccer","concacaf.nations")]

        urls = []
        for day in range(2):
            ds = (now + timedelta(days=day)).strftime("%Y%m%d")
            for sp, lg in leagues:
                urls.append((f"https://site.api.espn.com/apis/site/v2/sports/{sp}/{lg}/scoreboard?dates={ds}", lg, day))

        with ThreadPoolExecutor(max_workers=10) as exe:
            futures = {exe.submit(fetch_espn, u): (lg, d) for u, lg, d in urls}
            for f in futures:
                lg, day_offset = futures[f]
                data = f.result()
                if not data: continue
                
                for ev in data.get('events', []):
                    name = str(ev['name']).upper()
                    if name in seen: continue
                    
                    # NOUVEAU : On cherche la meilleure copie parmi toutes celles dispo
                    best_match = find_best_match_in_bible(name, bible, ev['date'], lg)
                    
                    if not best_match:
                        if day_offset >= 1: best_ch, final_score = "A_CONFIRMER", 10
                        else: continue
                    else:
                        best_ch = best_match['ch']
                        # Calcul du score final pour le tri des canaux CHOIX
                        final_score = PRIORITY_CONFIG["LEAGUES"].get(lg, 100) + best_match['quality']
                        
                        # Bonus d'équipe et de chaîne
                        for tk, bonus in PRIORITY_CONFIG["TEAMS"].items():
                            if tk in name: final_score += bonus
                        if lg == "nhl" and best_ch in CANADA_HOCKEY_IDS: final_score += PRIORITY_CONFIG["CHANNELS"]["BONUS_HOCKEY_CANADA"]

                    events.append({
                        "title": name, "score": final_score, "league": lg,
                        "start": datetime.strptime(ev['date'], "%Y-%m-%dT%H:%MZ"), 
                        "stop": datetime.strptime(ev['date'], "%Y-%m-%dT%H:%MZ") + timedelta(hours=3), 
                        "ch_key": best_ch
                    })
                    seen.add(name)

        # Répartition sur les 5 canaux (Sans doublons de source)
        events.sort(key=lambda x: x['score'], reverse=True)
        chans = {i: [] for i in range(1, 6)}
        for e in events:
            for i in range(1, 6):
                can_fit = True
                b_start = e['start'] - timedelta(minutes=30)
                for ex in chans[i]:
                    if not (e['stop'] <= ex['display_start'] or b_start >= ex['stop']):
                        can_fit = False; break
                
                # Vérifie si la source physique est déjà occupée ailleurs au même moment
                if can_fit and e['ch_key'] != "A_CONFIRMER":
                    for other_id in range(1, 6):
                        for other_ev in chans[other_id]:
                            if other_ev['ch_key'] == e['ch_key']:
                                if not (e['stop'] <= other_ev['start'] or e['start'] >= other_ev['stop']):
                                    can_fit = False; break
                
                if can_fit:
                    e['display_start'] = b_start
                    chans[i].append(e)
                    break

        CACHE_ORGANIZED = {"chans": chans, "timestamp": now}
        return chans

    # [Le reste des fonctions do_GET et generate_xml_output reste identique à la version stable précédente]
    
