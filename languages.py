"""Language support for Dirty Truth & Dare — 10 languages, native UI + content + voice.

Each language maps to:
- a human name (shown in the selector)
- a BCP-47 code (used to direct the LLM)
- a Kokoro TTS voice (verified available on the local engine)
- an RTL flag (Arabic)
- an example phrase (used to prime the LLM to write in that language)
"""

LANGUAGES = {
    "en": {
        "name": "English",
        "native": "English",
        "bcp47": "en",
        "voice": "af_heart",
        "rtl": False,
        "example": "",
    },
    "es": {
        "name": "Spanish",
        "native": "Español",
        "bcp47": "es",
        "voice": "ef_dora",
        "rtl": False,
        "example": "Acércate lentamente y susurra al oído de tu pareja: «me perteneces»",
    },
    "fr": {
        "name": "French",
        "native": "Français",
        "bcp47": "fr",
        "voice": "ff_siwis",
        "rtl": False,
        "example": "Approche-toi lentement et murmure à l'oreille de ton partenaire : « je t'appartiens »",
    },
    "de": {
        "name": "German",
        "native": "Deutsch",
        "bcp47": "de",
        "voice": "hf_alpha",
        "rtl": False,
        "example": "Komm langsam näher und flüstere deinem Partner ins Ohr: „Du gehörst mir“",
    },
    "it": {
        "name": "Italian",
        "native": "Italiano",
        "bcp47": "it",
        "voice": "if_sara",
        "rtl": False,
        "example": "Avvicinati lentamente e sussurra all'orecchio del tuo partner: «sei mio»",
    },
    "pt": {
        "name": "Portuguese",
        "native": "Português",
        "bcp47": "pt",
        "voice": "pf_dora",
        "rtl": False,
        "example": "Aproxime-se lentamente e sussurre no ouvido do seu parceiro: «você é meu»",
    },
    "hi": {
        "name": "Hindi",
        "native": "हिन्दी",
        "bcp47": "hi",
        "voice": "hf_alpha",  # closest available (Hindi not in Kokoro set)
        "rtl": False,
        "example": "धीरे से पास आओ और अपने साथी के कान में फुसफुसाओ: \"तुम मेरे हो\"",
    },
    "ja": {
        "name": "Japanese",
        "native": "日本語",
        "bcp47": "ja",
        "voice": "jf_alpha",
        "rtl": False,
        "example": "ゆっくりと近づき、パートナーの耳元で囁いてください：「あなたは私のもの」",
    },
    "zh": {
        "name": "Chinese",
        "native": "中文",
        "bcp47": "zh",
        "voice": "zf_xiaoni",
        "rtl": False,
        "example": "慢慢靠近，在你伴侣耳边低语：\"你是我的\"",
    },
    "ar": {
        "name": "Arabic",
        "native": "العربية",
        "bcp47": "ar",
        "voice": "hf_alpha",  # closest available (Arabic not in Kokoro set)
        "rtl": True,
        "example": "اقترب ببطء وهمس في أذن شريكك: \"أنت ملكي\"",
    },
}

DEFAULT_LANG = "en"


def get_lang(code):
    """Return the language dict for a code, falling back to English."""
    key = str(code or "").lower()
    if key not in LANGUAGES:
        key = DEFAULT_LANG
    d = dict(LANGUAGES[key])
    d["code"] = key
    return d


def language_directive(code):
    """Prompt fragment that forces the LLM to respond in the chosen language.
    Placed at the TOP of the system prompt for maximum primacy."""
    lang = get_lang(code)
    if lang["code"] == "en":
        return ""
    ex = lang.get("example", "")
    return (
        f"LANGUAGE RULE (absolute, overrides everything below):\n"
        f"You MUST write your entire response in {lang['name']} only. "
        f"Every single word — the title, every step instruction, every detail — "
        f"must be in {lang['name']}. Do NOT use any English words. "
        f"Do NOT mix English and {lang['name']}. If you catch yourself writing an "
        f"English word, translate it into {lang['name']} before outputting.\n"
        + (f"Example of a correct step instruction in {lang['name']}: \"{ex}\"\n" if ex else "")
        + "\n"
    )


def tts_voice(code):
    """Kokoro voice for a language code."""
    return get_lang(code)["voice"]


def is_rtl(code):
    return get_lang(code)["rtl"]
