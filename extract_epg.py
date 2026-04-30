import xml.etree.ElementTree as ET
import requests
import json
import gzip
from io import BytesIO
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Set, List, Optional
from abc import ABC, abstractmethod


# ==========================================
#                MODELS & CONFIGS
# ==========================================

@dataclass
class Programme:
    """Représente un programme TV filtré"""
    channel: str
    start: str
    stop: str
    title: str
    subtitle: str
    description: str
    category: str
    is_highlight: bool


@dataclass
class EPGSource:
    """Configuration d'une source EPG"""
    name: str
    url: str
    compressed: bool
    allowed_channels: Set[str]


class EPGConfig:
    """Configuration centralisée"""

    CHANNELS = {
        "canada": [
            "Réseau.des.Sports.(RDS).HD.ca2", "RDS2.HD.ca2", "Réseau.des.Sports.Info.HD.ca2",
            "TVA.Sports.HD.ca2", "TVA.Sports.2.HD.ca2", "Sportsnet.4K.ca2",
            "Sportsnet.One.HD.ca2", "Sportsnet.360.HD.ca2", "Sportsnet.East.HD.ca2",
            "Sportsnet.Ontario.HD.ca2", "Sportsnet.West.HD.ca2", "Sportsnet.(Pacific).HD.ca2",
            "Sportsnet.World.HD.ca2", "TSN.4K.ca2", "TSN.2.HD.ca2",
            "TSN.3.HD.ca2", "TSN.4.HD.ca2", "TSN.5.HD.ca2", "One.Soccer.ca2",
        ],
        "usa": [
            "ESPN.HD.us2", "ESPN2.HD.us2", "ESPN.Deportes.HD.us2",
            "beIN.Sports.USA.HD.us2", "BeInSports.Xtra.us2", "CBS.Sports.Network.HD.us2",
            "Fox.Sports.1.HD.us2", "Fox.Sports.2.HD.us2", "Fox.Soccer.Plus.HD.us2",
            "FuboSportsNetwork.us2", "GolazoSports.us2", "NBC.Sports.4K.us2",
        ],
        "uk": [
            "SkySp.F1.HD.uk", "SkySp.PL.HD.uk", "TNT.Sports.1.HD.uk",
            "TNT.Sports.2.HD.uk", "TNT.Sports.3.HD.uk", "TNT.Sports.4.HD.uk",
        ],
        "france": [
            "beIN.SPORTS.1.fr", "beIN.SPORTS.2.fr", "beIN.SPORTS.3.fr",
            "beIN.SPORTS.MAX.4.fr", "beIN.SPORTS.MAX.5.fr", "beIN.SPORTS.MAX.6.fr",
            "beIN.SPORTS.MAX.7.fr", "beIN.SPORTS.MAX.8.fr", "beIN.SPORTS.MAX.9.fr",
            "beIN.SPORTS.MAX.10.fr", "Canal+.fr", "Canal+.Sport.fr",
            "Canal+.Sport.360.fr", "Eurosport.1.fr", "Eurosport.2.fr",
            "CANAL+FOOT.fr", "RMC.Sport.1.fr",
        ],
    }

    SOURCES = [
        EPGSource(
            name="USA",
            url="https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
            compressed=True,
            allowed_channels=set(CHANNELS["usa"])
        ),
        EPGSource(
            name="UK",
            url="https://epgshare01.online/epgshare01/epg_ripper_UK1.xml.gz",
            compressed=True,
            allowed_channels=set(CHANNELS["uk"])
        ),
        EPGSource(
            name="France",
            url="https://epgshare01.online/epgshare01/epg_ripper_FR1.xml.gz",
            compressed=True,
            allowed_channels=set(CHANNELS["france"])
        ),
        EPGSource(
            name="Canada",
            url="https://epgshare01.online/epgshare01/epg_ripper_CA2.xml.gz",
            compressed=True,
            allowed_channels=set(CHANNELS["canada"])
        ),
    ]

    HL_KEYWORDS = ["RÉSUMÉ", "HIGHLIGHTS", "REPRISE", "CLASSIC", "REVUE", "TOP 10", "MAGAZINE", "DEBRIEF"]
    MIN_DURATION_MINUTES = 60
    EXCEPTIONS_TITLES = {"SC"}


# ==========================================
#                PARSERS
# ==========================================

class EPGParser(ABC):
    """Interface pour parser EPG"""

    @abstractmethod
    def parse(self, data: BytesIO) -> ET.Element:
        pass


class XMLTVParser(EPGParser):
    """Parser XMLTV utilisant iterparse"""

    def parse(self, data: BytesIO):
        return ET.iterparse(data, events=('end',))


# ==========================================
#                FILTERS
# ==========================================

class EPGFilter:
    """Logique de filtrage des programmes"""

    def __init__(self, config: EPGConfig = None):
        self.config = config or EPGConfig()

    def get_duration_minutes(self, start_str: str, stop_str: str) -> float:
        """Calcule la durée en minutes entre deux horaires"""
        try:
            fmt = "%Y%m%d%H%M%S" if len(start_str.split()[0]) > 12 else "%Y%m%d%H%M"
            start_time = datetime.strptime(start_str.split()[0], fmt)
            stop_time = datetime.strptime(stop_str.split()[0], fmt)
            return (stop_time - start_time).total_seconds() / 60
        except Exception:
            return 0

    def is_within_time_window(self, date_str: str) -> bool:
        """Vérifie si la date est dans la fenêtre de temps (48h passé, 4 jours futur)"""
        if not date_str:
            return False
        try:
            parts = date_str.split()
            clean_date = parts[0]
            tz_offset = parts[1] if len(parts) > 1 else "+0000"

            fmt = "%Y%m%d%H%M%S" if len(clean_date) > 12 else "%Y%m%d%H%M"
            prog_date = datetime.strptime(clean_date, fmt)

            # Parse timezone offset: "+0200" → hours=2, minutes=0
            sign = 1 if tz_offset[0] == '+' else -1
            hours = int(tz_offset[1:3])
            minutes = int(tz_offset[3:5])
            offset = timedelta(hours=sign * hours, minutes=sign * minutes)

            # Convert to UTC for comparison
            prog_date_utc = prog_date - offset

            now = datetime.utcnow()
            window_start = now - timedelta(hours=48)
            window_end = now + timedelta(days=4)
            return window_start <= prog_date_utc <= window_end
        except Exception:
            return False

    def should_keep_programme(self, channel: str, start: str, stop: str,
                             title: str, allowed_channels: Set[str]) -> bool:
        """Décide si un programme doit être conservé"""
        if channel not in allowed_channels:
            return False
        if not self.is_within_time_window(start):
            return False

        #duration = self.get_duration_minutes(start, stop)
        #if duration >= self.config.MIN_DURATION_MINUTES:
        #    return True
        #if title in self.config.EXCEPTIONS_TITLES:
        #    return True

        return True

    def is_highlight(self, title: str, subtitle: str, description: str) -> bool:
        """Détecte si un programme est un highlight"""
        content = f"{title} {subtitle} {description}".upper()
        return any(kw in content for kw in self.config.HL_KEYWORDS)


# ==========================================
#                DATA FETCHER
# ==========================================

class EPGFetcher:
    """Récupère et parse les données EPG"""

    TIMEOUT = 60

    @staticmethod
    def fetch(url: str, compressed: bool = False) -> ET.Element:
        """Télécharge et retourne le contenu (parsé si gzip)"""
        response = requests.get(url, timeout=EPGFetcher.TIMEOUT)
        response.raise_for_status()

        if compressed:
            data = gzip.GzipFile(fileobj=BytesIO(response.content))
        else:
            data = BytesIO(response.content)

        return data


# ==========================================
#                EXTRACTOR
# ==========================================

class EPGExtractor:
    """Orchestrateur principal"""

    def __init__(self, config: EPGConfig = None, output_file: str = "filtered_epg.json"):
        self.config = config or EPGConfig()
        self.filter = EPGFilter(self.config)
        self.parser = XMLTVParser()
        self.output_file = output_file

    def extract_programme(self, elem: ET.Element, allowed_channels: Set[str]) -> Optional[Programme]:
        """Extrait un programme depuis un élément XML"""
        channel = elem.get('channel')
        start = elem.get('start')
        stop = elem.get('stop')
        title = elem.findtext('title', 'Sport')

        if not self.filter.should_keep_programme(channel, start, stop, title, allowed_channels):
            return None

        subtitle = elem.findtext('sub-title', '')
        description = elem.findtext('desc', '')
        category = elem.findtext('category', '')

        return Programme(
            channel=channel,
            start=start,
            stop=stop,
            title=title,
            subtitle=subtitle,
            description=description,
            category=category,
            is_highlight=self.filter.is_highlight(title, subtitle, description)
        )

    def process_source(self, source: EPGSource) -> List[Programme]:
        """Traite une source EPG complète"""
        programmes = []

        try:
            print(f"Traitement source {source.name}...")
            data = EPGFetcher.fetch(source.url, source.compressed)

            context = self.parser.parse(data)
            for _, elem in context:
                if elem.tag == 'programme':
                    programme = self.extract_programme(elem, source.allowed_channels)
                    if programme:
                        programmes.append(programme)
                    elem.clear()

            print(f"-> {source.name}: {len(programmes)} programmes retenus.")
        except Exception as e:
            print(f"Erreur source {source.name}: {e}")

        return programmes

    def run(self) -> None:
        """Lance l'extraction complète"""
        print(f"--- DÉMARRAGE DE L'EXTRACTION ({datetime.utcnow().strftime('%H:%M:%S')} UTC) ---")

        all_programmes = []
        for source in self.config.SOURCES:
            all_programmes.extend(self.process_source(source))

        all_programmes.sort(key=lambda p: p.start or "")
        self.save(all_programmes)

        print(f"--- TOTAL FINAL: {len(all_programmes)} programmes ---")

    def save(self, programmes: List[Programme]) -> None:
        """Sauvegarde les programmes en JSON"""
        data = [
            {
                "ch": p.channel,
                "start": p.start,
                "stop": p.stop,
                "title": p.title,
                "sub-title": p.subtitle,
                "desc": p.description,
                "category": p.category,
                "is_highlight": p.is_highlight
            }
            for p in programmes
        ]

        with open(self.output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


# ==========================================
#                ENTRYPOINT
# ==========================================

if __name__ == "__main__":
    extractor = EPGExtractor()
    extractor.run()
