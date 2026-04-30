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
            "I123.15676.schedulesdirect.org", "I192.73271.schedulesdirect.org",
            "I124.39080.schedulesdirect.org", "I193.73142.schedulesdirect.org",
            "I1884.90206.schedulesdirect.org", "I405.62111.schedulesdirect.org",
            "I409.68858.schedulesdirect.org", "I410.49952.schedulesdirect.org",
            "I406.18798.schedulesdirect.org", "I408.18800.schedulesdirect.org",
            "I407.18801.schedulesdirect.org", "I401.18990.schedulesdirect.org",
            "I402.90118.schedulesdirect.org", "I403.90122.schedulesdirect.org",
            "I404.90124.schedulesdirect.org", "I420.57735.schedulesdirect.org",
        ],
        "france": [
            "CanalPlus.fr", "CanalPlusSport.fr", "CanalPlusSport360.fr",
            "beINSPORTS1.fr", "beINSPORTS2.fr", "beINSPORTS3.fr",
            "beINSPORTSMAX4.fr", "beINSPORTSMAX5.fr", "beINSPORTSMAX6.fr",
            "beINSPORTSMAX7.fr", "beINSPORTSMAX8.fr", "beINSPORTSMAX9.fr",
            "beINSPORTSMAX10.fr", "Eurosport1.fr", "Eurosport2.fr",
            "RMCSport1.fr", "RMCSport2.fr",
        ],
        "uk": [
            "I1241.82450.schedulesdirect.org", "I1246.82451.schedulesdirect.org",
            "I1248.95772.schedulesdirect.org", "I1099.116645.schedulesdirect.org",
            "I1081.87578.schedulesdirect.org",
        ],
        "usa": [
            "I206.32645.schedulesdirect.org", "I209.45507.schedulesdirect.org",
            "I301.25595.schedulesdirect.org", "I219.82541.schedulesdirect.org",
            "I221.16365.schedulesdirect.org", "I392.76942.gracenote.com",
        ],
    }

    SOURCES = [
        EPGSource(
            name="Canada/USA/UK",
            url="https://raw.githubusercontent.com/acidjesuz/EPGTalk/master/guide.xml",
            compressed=False,
            allowed_channels=set(CHANNELS["canada"] + CHANNELS["usa"] + CHANNELS["uk"])
        ),
        EPGSource(
            name="France",
            url="https://xmltvfr.fr/xmltv/xmltv_fr.xml.gz",
            compressed=True,
            allowed_channels=set(CHANNELS["france"])
        ),
        EPGSource(
            name="One Soccer CA2",
            url="https://epgshare01.online/epgshare01/epg_ripper_CA2.xml.gz",
            compressed=True,
            allowed_channels={"One.Soccer.ca2"}
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
            clean_date = date_str.split()[0]
            fmt = "%Y%m%d%H%M%S" if len(clean_date) > 12 else "%Y%m%d%H%M"
            prog_date = datetime.strptime(clean_date, fmt)
            now = datetime.utcnow()
            window_start = now - timedelta(hours=48)
            window_end = now + timedelta(days=4)
            return window_start <= prog_date <= window_end
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
