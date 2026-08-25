# yt-downloader

Application web pour télécharger des vidéos YouTube en `.mp4`, dans la qualité de ton choix — vidéo unique, playlist entière, ou liste de liens collés en une fois.

**Rien n'est stocké côté serveur.** Chaque téléchargement passe par un dossier temporaire créé à la volée, streamé directement vers le navigateur du client, puis supprimé dès que l'envoi est terminé. Aucun fichier vidéo, aucune métadonnée persistante, aucun volume Docker monté — le dossier `downloads/` n'existe pas, et `.gitignore` bloque tout média qui traînerait par erreur.

## Fonctionnalités

- **Vidéo unique** — colle un lien `youtube.com/watch?v=...`.
- **Playlist** — colle un lien `youtube.com/playlist?list=...`, chaque vidéo de la playlist est listée individuellement.
- **Liste de liens** — colle plusieurs liens (un par ligne, vidéos et/ou playlists mélangées), tout est résolu et affiché en une fois.
- **Choix de la qualité** — sélecteur global (appliqué par défaut à chaque résultat) + sélecteur par vidéo (2160p → 360p, ou "meilleure disponible"). yt-dlp retombe automatiquement sur la qualité immédiatement inférieure si celle demandée n'existe pas pour une vidéo donnée.
- **Sortie** — toujours du `.mp4` (fusion vidéo+audio via ffmpeg si nécessaire).

## Architecture

```
app/
  main.py         FastAPI : endpoints API + sert le frontend statique
  downloader.py   Wrapper yt-dlp (résolution de liens, téléchargement en tmpdir éphémère)
  models.py       Schémas Pydantic des requêtes
  static/         Frontend (HTML/CSS/JS vanilla, aucun build requis)
```

### Comment "rien n'est stocké" est garanti

1. `/api/resolve` n'écrit jamais sur disque : il utilise `yt-dlp` avec `skip_download=True` pour ne récupérer que les métadonnées (titre, miniature, durée, qualités disponibles).
2. `/api/download` crée un `tempfile.mkdtemp()` unique par requête, y télécharge une seule vidéo, la renvoie via une réponse **streamée** (`FileResponse`), puis un `BackgroundTask` supprime le dossier temporaire juste après l'envoi — succès ou échec.
3. Aucun volume Docker n'est monté sur le conteneur : un redémarrage efface tout ce qui aurait pu traîner.

## Démarrer

### Avec Docker (recommandé)

```bash
docker compose up --build
```

Puis ouvre [http://localhost:8000](http://localhost:8000).

### En local (sans Docker)

Prérequis : Python 3.11+, [ffmpeg](https://ffmpeg.org/download.html) installé et présent dans le `PATH`.

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## API

| Méthode | Route | Description |
|---|---|---|
| `POST` | `/api/resolve` | `{"urls": ["...", "..."]}` → liste d'items résolus (titre, miniature, durée, qualités disponibles, ou erreur par lien). |
| `GET` | `/api/download?url=...&quality=1080p` | Télécharge et stream un `.mp4` unique. `quality` accepte `best`, `2160p`, `1440p`, `1080p`, `720p`, `480p`, `360p`. |
| `GET` | `/api/health` | Healthcheck. |

## Avertissement

Cet outil s'appuie sur [`yt-dlp`](https://github.com/yt-dlp/yt-dlp). Il est fourni à des fins personnelles et éducatives : à toi de respecter les conditions d'utilisation de YouTube et les droits d'auteur des contenus que tu télécharges (contenu qui t'appartient, licences libres, usage privé autorisé, etc.). Ne l'utilise pas pour redistribuer du contenu protégé sans autorisation.

## Licence

MIT — voir [LICENSE](LICENSE).
