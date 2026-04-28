from flask import Flask, Response, request, redirect, make_response
import requests
from datetime import datetime, timedelta
import pytz

app = Flask(__name__)

# --- CONFIG DE BASE ---
USER = "tDcJnv4jMM"
PASS = "2khBtbUZuV"
BASE_DOMAIN = "omegatv.live:80"

def get_url(cid):
    return f"http://{BASE_DOMAIN}/{USER}/{PASS}/{cid}.ts"

# --- ROUTES ---
@app.route('/')
def home():
    return "Le serveur Flask fonctionne sur Vercel !"

@app.route('/nhl-live/<ch>')
def live(ch):
    # On force RDS pour le test de 404
    target = get_url("184813") 
    res = make_response(redirect(target, code=302))
    res.headers['User-Agent'] = 'IPTVSmarters/1.0.3'
    return res

@app.route('/playlist.m3u')
def playlist():
    host = request.host_url.rstrip('/')
    m3u = ["#EXTM3U"]
    for i in range(1, 6):
        m3u.append(f'#EXTINF:-1 tvg-id="MULTI{i}", MULTI {i}\n{host}/nhl-live/{i}')
    return Response("\n".join(m3u), mimetype='text/plain')

# C'est crucial pour Vercel
if __name__ == '__main__':
    app.run()
    
