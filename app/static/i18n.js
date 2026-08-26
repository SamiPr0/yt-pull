// Frontend translation table. Add a new language by adding a key here (and
// its mirror in app/i18n.py for server-side error messages) — nothing else
// needs to change, langSelect and t() both read this object.
const TRANSLATIONS = {
  en: {
    langName: "English",
    pageTitle: "yt-pull — Free YouTube Downloader",
    metaDescription:
      "Paste a link, pick a quality, get an MP4. Free YouTube downloader for single videos, playlists, or a batch of links — nothing stored on the server.",
    githubLinkText: "Source on GitHub",
    tagline: "Free YouTube downloader — paste a link, pick your quality, get your MP4.",
    step1: "Paste link(s)",
    step2: "Pick a quality",
    step3: "Download",
    urlsLabel: "YouTube link(s)",
    urlsPlaceholder:
      "Paste a video link, a playlist link, or several links (one per line)\nhttps://www.youtube.com/watch?v=...\nhttps://www.youtube.com/playlist?list=...",
    clear: "Clear",
    analyze: "Analyze",
    analyzing: "Analyzing...",
    pasteAtLeastOne: "Paste at least one YouTube link.",
    unknownError: "Unknown error.",
    somethingWrong: "Something went wrong.",
    noneLookValid: "None of these look like YouTube links — check them before analyzing.",
    someInvalid: (n, total) => `${n} of ${total} link(s) don't look like YouTube links and will likely fail.`,
    results: (n) => `Results (${n})`,
    qualityForAll: "Quality for all",
    bestAvailable: "Best available",
    selectAll: "Select all",
    downloadSelected: (n) => `Download selected (${n})`,
    rateLimitWarning: (n, limit) =>
      `${n} selected — downloads are limited to ${limit}/min, so this batch will pace itself and take longer.`,
    download: "Download",
    selectThisVideo: "Select this video",
    back: "Back",
    downloadsHeading: "Downloads",
    noDownloadsYet: "No downloads yet.",
    cancel: "Cancel",
    retry: "Retry",
    done: "Done ✓",
    started: "Started ✓",
    waitingForServer: "Waiting for server...",
    stillWorking: (s) => `Still working — fetching and processing the video... (${s}s)`,
    cancelled: "Cancelled",
    queuedWaiting: (s) => `Queued — waiting ${s}s (rate limit)`,
    pacing: (s) => `Pacing downloads (rate limit)... ${s}s`,
    almostDone: "almost done",
    secLeft: (s) => `${s}s left`,
    minSecLeft: (m, s) => `${m}m ${s}s left`,
    disclaimerPre: "Personal tool built on",
    disclaimerPost:
      "Respect copyright and YouTube's terms of service: only download content you have the right to save.",
    languageLabel: "Language",
  },
  fr: {
    langName: "Français",
    pageTitle: "yt-pull — Téléchargeur YouTube gratuit",
    metaDescription:
      "Colle un lien, choisis une qualité, récupère un MP4. Téléchargeur YouTube gratuit pour vidéos, playlists ou lots de liens — rien n'est stocké sur le serveur.",
    githubLinkText: "Code source sur GitHub",
    tagline: "Téléchargeur YouTube gratuit — colle un lien, choisis ta qualité, récupère ton MP4.",
    step1: "Colle le(s) lien(s)",
    step2: "Choisis une qualité",
    step3: "Télécharge",
    urlsLabel: "Lien(s) YouTube",
    urlsPlaceholder:
      "Colle un lien de vidéo, de playlist, ou plusieurs liens (un par ligne)\nhttps://www.youtube.com/watch?v=...\nhttps://www.youtube.com/playlist?list=...",
    clear: "Effacer",
    analyze: "Analyser",
    analyzing: "Analyse...",
    pasteAtLeastOne: "Colle au moins un lien YouTube.",
    unknownError: "Erreur inconnue.",
    somethingWrong: "Une erreur est survenue.",
    noneLookValid: "Aucun de ces liens ne ressemble à un lien YouTube — vérifie avant d'analyser.",
    someInvalid: (n, total) => `${n} lien(s) sur ${total} ne ressemblent pas à des liens YouTube et échoueront probablement.`,
    results: (n) => `Résultats (${n})`,
    qualityForAll: "Qualité pour tous",
    bestAvailable: "Meilleure disponible",
    selectAll: "Tout sélectionner",
    downloadSelected: (n) => `Télécharger la sélection (${n})`,
    rateLimitWarning: (n, limit) =>
      `${n} sélectionnée(s) — les téléchargements sont limités à ${limit}/min, ce lot prendra donc plus de temps.`,
    download: "Télécharger",
    selectThisVideo: "Sélectionner cette vidéo",
    back: "Retour",
    downloadsHeading: "Téléchargements",
    noDownloadsYet: "Aucun téléchargement pour l'instant.",
    cancel: "Annuler",
    retry: "Réessayer",
    done: "Terminé ✓",
    started: "Lancé ✓",
    waitingForServer: "En attente du serveur...",
    stillWorking: (s) => `Toujours en cours — récupération et traitement de la vidéo... (${s}s)`,
    cancelled: "Annulé",
    queuedWaiting: (s) => `En attente — ${s}s (limite de débit)`,
    pacing: (s) => `Téléchargements espacés (limite de débit)... ${s}s`,
    almostDone: "presque terminé",
    secLeft: (s) => `${s}s restantes`,
    minSecLeft: (m, s) => `${m}min ${s}s restantes`,
    disclaimerPre: "Outil personnel basé sur",
    disclaimerPost:
      "Respecte les droits d'auteur et les conditions d'utilisation de YouTube : ne télécharge que du contenu que tu as le droit d'enregistrer.",
    languageLabel: "Langue",
  },
};

const DEFAULT_LANG = "en";
const SUPPORTED_LANGS = Object.keys(TRANSLATIONS);

function getLang() {
  const stored = localStorage.getItem("lang");
  return SUPPORTED_LANGS.includes(stored) ? stored : DEFAULT_LANG;
}

function setLang(lang) {
  if (!SUPPORTED_LANGS.includes(lang)) return;
  localStorage.setItem("lang", lang);
}

function t(key, ...args) {
  const lang = getLang();
  const dict = TRANSLATIONS[lang] || TRANSLATIONS[DEFAULT_LANG];
  const entry = dict[key] ?? TRANSLATIONS[DEFAULT_LANG][key] ?? key;
  return typeof entry === "function" ? entry(...args) : entry;
}
