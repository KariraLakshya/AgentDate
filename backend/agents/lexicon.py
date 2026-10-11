"""Keyword lexicon shared by the offline (mock) analyst and referee.

Every concept maps to regexes; the analyst only ever reports a concept together with a LITERAL substring of the
source text that matched. No sensitive categories (religion, orientation, gender identity, health, politics,
ethnicity) are represented here.
"""
import re

# category -> list of (label, pattern)
_RAW: dict[str, list[tuple[str, str]]] = {
    "hobbies": [
        ("rock climbing", r"\bclimb\w*|\bboulder\w*"),
        ("trail running", r"\btrail[- ]run\w*|\bultra[- ]?run\w*|\bjogg\w*|\brunning\b"),
        ("cooking", r"\bcook(?:ing|s|ed)?\b|\brecipes?\b|\bsourdough\b|\bkitchen\b"),
        ("baking", r"\bbak(?:e|es|ing|ed|er)\b|\bpastr(?:y|ies)\b"),
        ("photography", r"\bphotograph\w*|\bfilm camera\b|\b35mm\b"),
        ("gardening", r"\bgarden\w*|\ballotment\b|\bhouseplants?\b"),
        ("board games", r"\bboard ?games?\b|\btabletop\b|\bdungeons\b"),
        ("painting", r"\bpaint(?:ing|s|ed)?\b|\bwatercolou?rs?\b|\bsketch\w*"),
        ("pottery", r"\bpottery\b|\bceramics?\b"),
        ("cycling", r"\bcycl(?:e|ing|ist)\b|\bbikepack\w*|\bgravel bike\b"),
        ("hiking", r"\bhik(?:e|es|ing|ed)\b|\btrek\w*|\bsummit\w*"),
        ("live music", r"\bgigs?\b|\bconcerts?\b|\blive music\b|\bvinyl\b|\bfestivals?\b"),
        ("playing music", r"\bguitar\b|\bpiano\b|\bdrums\b|\bviolin\b|\bsynth\w*"),
        ("reading", r"\bbook ?clubs?\b|\bnovels?\b|\breading\b|\bbookshop\w*"),
        ("travel", r"\btravel\w*|\bbackpack\w*|\bpassport\b|\broad ?trip\w*"),
        ("video games", r"\bvideo ?games?\b|\bgaming\b|\bspeedrun\w*"),
        ("yoga", r"\byoga\b|\bpilates\b"),
        ("swimming", r"\bswim\w*"),
        ("surfing", r"\bsurf\w*|\bpaddle ?board\w*"),
        ("chess", r"\bchess\b"),
        ("creative writing", r"\bjournal\w*|\bpoetry\b|\bzines?\b|\bshort stories\b"),
        ("volunteering", r"\bvolunteer\w*"),
        ("film and cinema", r"\bcinema\b|\bfilms?\b|\bmovies?\b"),
        ("coffee", r"\bcoffee\b|\bespresso\b"),
        ("dancing", r"\bsalsa\b|\bdanc(?:e|es|ing)\b"),
        ("thrifting", r"\bthrift\w*|\bvintage\b|\bflea market\w*"),
        ("sailing and kayaking", r"\bsail\w*|\bkayak\w*|\bcanoe\w*"),
        ("birdwatching", r"\bbird ?watch\w*|\bbirding\b"),
        ("woodworking", r"\bwoodwork\w*|\bcarpentry\b"),
        ("knitting and sewing", r"\bknit\w*|\bcrochet\w*|\bsewing\b"),
        ("gym and strength training", r"\bgym\b|\bweightlift\w*|\bstrength training\b"),
        ("karaoke", r"\bkaraoke\b"),
    ],
    "interests": [
        ("AI and machine learning", r"\bmachine learning\b|\bAI\b|\bLLMs?\b"),
        ("climate and sustainability", r"\bclimate\b|\bsustainab\w*|\brenewables?\b|\bcarbon\b"),
        ("urban planning and transit", r"\burban\b|\bcity planning\b|\btransit\b|\bwalkable\b"),
        ("design", r"\bdesign\w*|\btypograph\w*"),
        ("startups", r"\bstartups?\b|\bfounder\b|\bco-?founded?\b"),
        ("teaching and mentoring", r"\bteach\w*|\bmentor\w*|\btutor\w*"),
        ("finance and economics", r"\bfinanc\w*|\beconomic\w*|\binvest\w*|\bbudget\w*"),
        ("space and astronomy", r"\bastronom\w*|\btelescope\b|\bspace missions?\b"),
        ("history", r"\bhistor(?:y|ical)\b|\barchaeolog\w*|\bmuseums?\b"),
        ("food and restaurants", r"\bfood\b|\brestaurants?\b|\bstreet food\b|\bfoodie\b"),
        ("architecture", r"\barchitect\w*|\bbrutalis\w*"),
        ("data and analytics", r"\bdata\b|\banalytics\b|\bstatistic\w*"),
        ("open source", r"\bopen[- ]source\b"),
        ("robotics and electronics", r"\brobot\w*|\bhardware\b|\belectronics\b|\bsoldering\b|\b3d print\w*"),
        ("psychology and behaviour", r"\bpsycholog\w*|\bbehaviou?r\w*"),
        ("language learning", r"\blanguage learning\b|\blearning (?:spanish|japanese|italian|french|german|portuguese)\b"),
        ("podcasts", r"\bpodcasts?\b"),
        ("sci-fi and fantasy", r"\bsci-?fi\b|\bscience fiction\b|\bfantasy\b"),
        ("wildlife and conservation", r"\bwildlife\b|\bconservation\b|\becolog\w*"),
        ("cybersecurity", r"\bsecurity\b|\bcyber\w*|\bencrypt\w*"),
        ("logistics and operations", r"\bsupply chain\b|\blogistics\b|\boperations\b"),
        ("fashion and textiles", r"\bfashion\b|\btextiles?\b"),
    ],
    "values": [
        ("honesty and directness", r"\bhonest\w*|\bcandid\b|\bdirect\b|\btransparen\w*|\bstraight talk\b"),
        ("family", r"\bfamily\b|\bmy (?:parents|sister|brother|grandm\w+|grandf\w+)\b|\bsiblings?\b"),
        ("community", r"\bcommunity\b|\bneighbou?r\w*|\bgiving back\b"),
        ("curiosity", r"\bcuriou\w*|\bcuriosity\b|\balways learning\b|\blifelong learn\w*"),
        ("ambition", r"\bambiti\w*|\bdriven\b|\bship it\b"),
        ("work-life balance", r"\bwork-life\b|\bbalance\b|\bboundaries\b|\bswitch off\b"),
        ("adventure", r"\badventur\w*|\bspontaneous\b|\bspontaneity\b"),
        ("creativity", r"\bcreativ\w*|\bmaker\b|\bimagin\w*"),
        ("kindness and empathy", r"\bkind\w*|\bempath\w*|\bcompassion\w*|\bgentle\b"),
        ("independence", r"\bindependen\w*|\bautonom\w*|\bself-reliant\b"),
        ("stability and planning", r"\bstabil\w*|\broutine\b|\bplan ahead\b|\borganis\w*|\borganiz\w*"),
        ("integrity", r"\bintegrity\b|\bethic\w*|\bfairness\b"),
        ("growth", r"\bgrowth mindset\b|\bself-improvement\b|\bgrowing\b"),
        ("loyalty and commitment", r"\bloyal\w*|\bcommitment\b|\bcommitted\b|\bshow up for\b"),
    ],
    "lifestyle": [
        ("early riser", r"\bearly[- ]morning\b|\b5 ?am\b|\bsunrise\b|\bearly riser\b|\bearly bird\b|\bdawn\b"),
        ("night owl", r"\bnight owl\b|\blate[- ]night\b|\bmidnight\b"),
        ("homebody", r"\bhomebod\w*|\bcosy\b|\bcozy\b|\bstay(?:ing)? in\b"),
        ("city living", r"\bcity (?:life|living)\b|\bneighbou?rhood\b"),
        ("remote and mobile", r"\bremote\b|\bdigital nomad\b|\bon the road\b"),
        ("outdoorsy", r"\boutdoors?\b|\bcamping\b|\bfresh air\b"),
        ("social host", r"\bdinner part\w*|\bhosting\b|\bgame night\b|\bbrunch\w*"),
        ("pet owner", r"\bmy dog\b|\bmy cat\b|\bpuppy\b"),
        ("minimalist", r"\bminimalis\w*|\bdeclutter\w*"),
        ("frequent traveller", r"\bfrequent flyer\b|\bconference circuit\b|\btravel for work\b"),
        ("training routine", r"\bmorning run\b|\bworkout\w*|\btraining plan\b|\btraining block\b"),
    ],
    "needs": [
        ("time to recharge", r"\brecharg\w*|\bdowntime\b|\balone time\b|\bquiet time\b|\bsolitude\b"),
        ("novelty and adventure", r"\bnew places\b|\bsomething new\b|\bitchy feet\b"),
        ("intellectual stimulation", r"\bdeep conversations?\b|\bdebate\w*|\bgood argument\b|\bbig questions\b"),
        ("close social connection", r"\bmy people\b|\bconnection\b|\bbelong\w*"),
        ("physical movement", r"\bneed to move\b|\bget outside\b|\bfresh air\b|\bsweat\b"),
        ("a creative outlet", r"\bcreative outlet\b|\bmake things\b|\bmaking things\b"),
        ("structure and routine", r"\bstructure\b|\broutines?\b|\bclear plan\b"),
        ("autonomy", r"\bspace to\b|\bfreedom\b|\bautonomy\b"),
    ],
}

CONCEPTS: dict[str, list[tuple[str, re.Pattern]]] = {
    cat: [(label, re.compile(p, re.I)) for label, p in items] for cat, items in _RAW.items()
}

WANTS_PATTERN = re.compile(
    r"\blooking for\b|\bsomeone who\b|\bpartner in\b|\bmy person\b|\bhoping to meet\b|\bwant a partner\b", re.I
)

COMM_STYLES = [
    ("direct and concise", re.compile(r"\bdirect\b|\bblunt\b|\bstraight talk\b|\bno fluff\b|\bconcise\b", re.I)),
    ("warm storyteller", re.compile(r"\bstorytell\w*|\blistener\b|\bwarm\b|\bchatty\b|\blong conversations\b", re.I)),
    ("analytical and precise", re.compile(r"\bdata-?driven\b|\bevidence\b|\banalytic\w*|\bprecise\b|\bfirst principles\b", re.I)),
    ("playful and teasing", re.compile(r"\bbanter\b|\btease\w*|\bplayful\b|\blol\b", re.I)),
    ("thoughtful and reserved", re.compile(r"\bquiet\b|\bthoughtful\b|\breserved\b|\blisten first\b|\bintrovert\w*", re.I)),
]
HUMORS = [
    ("dry and deadpan", re.compile(r"\bdry\b|\bdeadpan\b|\bsarcas\w*|\bunderstatement\b", re.I)),
    ("punny and silly", re.compile(r"\bpuns?\b|\bdad jokes?\b|\bmemes?\b|\bgoofy\b|\bsilly\b|\bhaha\w*|\blol\b", re.I)),
    ("absurdist", re.compile(r"\babsurd\w*|\bsurreal\b|\bchaos\b|\bunhinged\b|\bgoblin\b", re.I)),
    ("self-deprecating", re.compile(r"\bself-deprecat\w*|\bterrible at\b|\bdisaster\b", re.I)),
    ("wry and observational", re.compile(r"\bobservational\b|\bwhimsical\b|\bwry\b", re.I)),
]
ENERGIES = [
    ("high and restless", re.compile(r"\benergetic\b|\bbuzz\w*|\bon the move\b|\bnever sit still\b|\bmarathon\w*|\b5 ?am\b|\bhigh-energy\b", re.I)),
    ("calm and steady", re.compile(r"\bcalm\b|\bslow\b|\bsteady\b|\bunhurried\b|\bcosy\b|\bmellow\b", re.I)),
]

PLAYFUL_TONE = re.compile(r"\blol\b|\bhaha\w*|\bchaos\b|\bgoblin\b|\bunhinged\b|\bmemes?\b|\bvibes\b|!!|😂|🤪", re.I)
FORMAL_TONE = re.compile(
    r"\bstakeholders?\b|\bleverag\w*|\bscalab\w*|\broadmap\b|\bKPIs?\b|\bstrateg\w*|\benterprise\b|\bcross-functional\b|\bsynerg\w*|\bdeliver\w*",
    re.I,
)

# Post-filter: forbidden inference categories (spec hard constraint 3).
SENSITIVE = {
    "religion": re.compile(
        r"\b(?:christian\w*|muslim\w*|islam\w*|jewish|judaism|hindu\w*|buddhis\w*|sikh\w*|atheis\w*|agnostic\w*|"
        r"church|mosque|synagogue|temple worship|prayer|praying|religio\w*|faith|devout|spiritual\w*)\b",
        re.I,
    ),
    "sexual_orientation": re.compile(
        r"\b(?:gay|lesbian|bisexual|homosexual|heterosexual|queer|lgbt\w*|asexual|pansexual|sexual orientation)\b", re.I
    ),
    "gender_identity": re.compile(
        r"\b(?:transgender|trans (?:man|woman)|non-?binary|genderqueer|gender identity|gender fluid|genderfluid|cisgender)\b", re.I
    ),
    "health": re.compile(
        r"\b(?:diagnos\w*|depress\w*|anxiety|anxious|cancer|diabet\w*|chronic (?:illness|pain|condition)|disabilit\w*|disabled|"
        r"mental health|medication|therapy|therapist|adhd|autis\w*|bipolar|pregnan\w*|illness|sober|addict\w*|eating disorder|"
        r"health condition|ptsd)\b",
        re.I,
    ),
    "politics": re.compile(
        r"\b(?:democrat\w*|republican\w*|conservative\w*|liberal\w*|left-wing|right-wing|socialis\w*|communis\w*|maga|"
        r"political (?:party|views|leaning)|vote[sd]? for|trump|brexit|partisan|leftist|far-right|far-left)\b",
        re.I,
    ),
    "ethnicity": re.compile(
        r"\b(?:ethnic\w*|ethnicity|racial|racially|(?:my|her|his|their) race|caucasian|hispanic|latino|latina|latinx|african[- ]american|asian[- ]american|"
        r"indigenous|immigrant\w*|skin colou?r|people of colou?r)\b",
        re.I,
    ),
}


def sensitive_categories(text: str) -> list[str]:
    return [name for name, rx in SENSITIVE.items() if rx.search(text or "")]


def concepts_in(text: str, categories=("hobbies", "interests", "values", "lifestyle", "needs")) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for cat in categories:
        out[cat] = {label for label, rx in CONCEPTS[cat] if rx.search(text or "")}
    return out
