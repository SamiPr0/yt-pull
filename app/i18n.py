"""Tiny server-side translation table for API-facing messages (the ones
that end up displayed directly in the frontend). Mirrors app/static/i18n.js
on the frontend side."""

SUPPORTED_LANGS = ("en", "fr")
DEFAULT_LANG = "en"

MESSAGES = {
    "no_link": {
        "en": "No link provided.",
        "fr": "Aucun lien fourni.",
    },
    "too_many_links": {
        "en": "Maximum 25 links at once.",
        "fr": "Maximum 25 liens à la fois.",
    },
    "invalid_url": {
        "en": "Invalid URL: {url}",
        "fr": "URL invalide : {url}",
    },
    "youtube_only": {
        "en": "Only YouTube links are accepted: {url}",
        "fr": "Seuls les liens YouTube sont acceptés : {url}",
    },
    "resolve_failed": {
        "en": "Could not read this link: {error}",
        "fr": "Impossible de lire ce lien : {error}",
    },
    "no_info": {
        "en": "No information found for this link.",
        "fr": "Aucune information trouvée pour ce lien.",
    },
    "no_file_produced": {
        "en": "The download did not produce any file.",
        "fr": "Le téléchargement n'a produit aucun fichier.",
    },
    "download_failed": {
        "en": "Download failed: {error}",
        "fr": "Échec du téléchargement : {error}",
    },
    "rate_limited": {
        "en": "Too many requests. Please slow down and try again in a minute.",
        "fr": "Trop de requêtes. Ralentis et réessaie dans une minute.",
    },
    "untitled": {
        "en": "Untitled",
        "fr": "Sans titre",
    },
    "playlist_fallback": {
        "en": "Playlist",
        "fr": "Liste de lecture",
    },
}


def normalize_lang(lang: str | None) -> str:
    return lang if lang in SUPPORTED_LANGS else DEFAULT_LANG


def t(key: str, lang: str | None = None, **kwargs) -> str:
    lang = normalize_lang(lang)
    template = MESSAGES.get(key, {}).get(lang) or MESSAGES.get(key, {}).get(DEFAULT_LANG) or key
    return template.format(**kwargs) if kwargs else template
