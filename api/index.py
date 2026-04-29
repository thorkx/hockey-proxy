# Noms simplifiés pour l'affichage propre dans le titre
CH_NAMES = {
    # RDS / TVA (Québec)
    "I123.15676.schedulesdirect.org": "RDS",
    "I124.15677.schedulesdirect.org": "RDS 2",
    "I125.15678.schedulesdirect.org": "RDS Info",
    "I154.58314.schedulesdirect.org": "TVA Sports",
    "I155.58315.schedulesdirect.org": "TVA Sports 2",
    "I156.58316.schedulesdirect.org": "TVA Sports 3",
    
    # TSN (Canada)
    "I111.15670.schedulesdirect.org": "TSN 1",
    "I112.15671.schedulesdirect.org": "TSN 2",
    "I113.15672.schedulesdirect.org": "TSN 3",
    "I114.15673.schedulesdirect.org": "TSN 4",
    "I115.15674.schedulesdirect.org": "TSN 5",
    
    # Sportsnet (Canada)
    "I408.18800.schedulesdirect.org": "SN West",
    "I409.18801.schedulesdirect.org": "SN East",
    "I410.18802.schedulesdirect.org": "SN Ontario",
    "I411.18803.schedulesdirect.org": "SN Pacific",
    "I412.18804.schedulesdirect.org": "SN One",
    "I413.18805.schedulesdirect.org": "SN 360",
    
    # Soccer / International (DAZN, Apple, etc.)
    "I212.12345.schedulesdirect.org": "DAZN 1",
    "I213.12346.schedulesdirect.org": "DAZN 2",
    "I900.00001.schedulesdirect.org": "Apple TV MLS",
    "I446.52300.schedulesdirect.org": "Sky MX / La Liga",
    "I500.67890.schedulesdirect.org": "beIN Sports",
    "I303.54321.schedulesdirect.org": "Canal+"
}

# Mapping vers tes flux IPTV réels (Extraits de ta playlist)
STREAM_MAP = {
    # RDS / TVA
    "I123.15676.schedulesdirect.org": "71151", # RDS HD (QC)
    "I124.15677.schedulesdirect.org": "71152", # RDS 2 HD
    "I154.58314.schedulesdirect.org": "71165", # TVA SPORTS HD
    "I155.58315.schedulesdirect.org": "71166", # TVA SPORTS 2 HD
    
    # TSN
    "I111.15670.schedulesdirect.org": "71243", # TSN 1
    "I112.15671.schedulesdirect.org": "71244", # TSN 2
    "I113.15672.schedulesdirect.org": "71245", # TSN 3
    "I114.15673.schedulesdirect.org": "71246", # TSN 4
    "I115.15674.schedulesdirect.org": "71247", # TSN 5
    
    # Sportsnet
    "I410.18802.schedulesdirect.org": "71236", # SN Ontario
    "I409.18801.schedulesdirect.org": "71234", # SN East
    "I408.18800.schedulesdirect.org": "71237", # SN West
    "I411.18803.schedulesdirect.org": "71235", # SN Pacific
    "I412.18804.schedulesdirect.org": "71233", # SN One
    "I413.18805.schedulesdirect.org": "71232", # SN 360
    
    # DAZN / Soccer (Exemples basés sur les structures standards)
    "I212.12345.schedulesdirect.org": "184900", # DAZN 1
    "I213.12346.schedulesdirect.org": "184901", # DAZN 2
    "I900.00001.schedulesdirect.org": "185000", # MLS Season Pass
    "I446.52300.schedulesdirect.org": "184950"  # La Liga TV
}
