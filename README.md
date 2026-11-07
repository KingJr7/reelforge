# reelforge

Moteur de montage vidéo programmatique en Python — produit des Reels/Shorts/TikTok verticaux
(1080×1920, 30 fps, H.264 + AAC) à partir d'un script annoté.

## Installation

```bash
cd reelforge
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Vérifier FFmpeg :
```bash
ffmpeg -version   # doit afficher la version
ffprobe -version
```

## Configuration

Copier `.env.example` vers `.env` et remplir les clés :

```bash
cp .env.example .env
```

Éditer `.env` avec :
- `ELEVENLABS_API_KEY` et `ELEVENLABS_VOICE_ID` (pour la voix)
- `PEXELS_API_KEY` (pour les B-rolls)

## Utilisation

### Mode démo (sans aucune clé)

Génère une vidéo complète avec voix factice, B-rolls synthétiques, SFX synthétiques :

```bash
python make_reel.py --script example_script.txt --demo --preview --out out/demo.mp4
python verify.py out/demo.mp4 --timeline out/timeline.json
```

### Production (avec clés API)

```bash
python make_reel.py --script scripts/mon_sujet.txt --out out/mon_reel.mp4
```

### Prototype motion design HTML

Pour tester le nouveau moteur de scènes graphiques générées en HTML/CSS :

```bash
python3 html_motion_renderer.py --duration 6 --out out/html_motion_demo.mp4
```

Le backend est aussi disponible dans le pipeline principal :

```bash
python3 make_reel.py --script scripts/levelcash_v1_humain.txt --voice-file v1.mp3 \
  --engine hybrid --html-template auto --preview --out out/levelcash_hybrid.mp4
```

`classic` reste le backend par défaut. `html` rend la scène HTML sur toute la durée ; `hybrid` combine une intro HTML avec le renderer classique en conservant la timeline audio complète. Templates disponibles : `auto`, `hero`, `numbers`, `split`, `cta`, `diagram`, `comparison`, `broll`.

Pour choisir précisément les scènes HTML, utilisez un plan utilisateur :

```bash
python3 make_reel.py --script scripts/mon_sujet.txt --voice-file v1.mp3 \
  --engine hybrid --scene-plan html-scene-plan.example.json --out out/custom.mp4
```

Le plan contient au moins deux fenêtres contiguës. Chaque fenêtre peut utiliser `html` ou `classic`, avec son propre template ; voir `html-scene-plan.example.json`.

La page est évaluée frame par frame, capturée en PNG puis encodée avec FFmpeg. Le moteur utilise Playwright/Chromium si disponible et `wkhtmltoimage` en fallback.

Première passe en `--preview` pour valider rapidement, puis rendu final en 1080×1920.

### Options CLI

| Option | Description |
|--------|-------------|
| `--script FICHIER` | Script annoté (requis) |
| `--out FICHIER` | MP4 de sortie (défaut : out/reel.mp4) |
| `--bgm FICHIER` | Musique de fond (optionnel) |
| `--flow sweep\|mirror` | Continuité directionnelle (défaut : sweep) |
| `--invert-at 0.0-1.0` | Moment de l'inversion palette |
| `--glitch-frames N` | Frames de glitch après inversion (défaut : 4) |
| `--duck-db -22` | Ducking BGM pendant la voix (dB) |
| `--preview` | Rendu 540×960 rapide |
| `--demo` | Sans clé API ni asset |
| `--debug` | Affiche timecode + événement courant |
| `--keep-temp` | Garde mix.wav temporaire |
| `--force-voice` | Régénère la voix même si cache |
| `--list-voices` | Liste les voix ElevenLabs |

## Format du script annoté

```
Tu savais qu'il existe [BROLL: robot hand typing | 1.8s | medium] une façon de gagner *deux heures* par jour ? [PAUSE 0.3]
Et le plus fou, c'est que tu peux la tester dès **aujourd'hui**. [BROLL: laptop coding | 2.0s | medium video]
[INVERT] Fini la fatigue, fini les tâches répétitives.
[CTA: MONSITE.COM]
```

Marqueurs :
- `[BROLL: requête | durée | size]` — carte B-roll (size : small/medium/large, ajoute `video` pour préférer une vidéo)
- `[INVERT]` — bascule clair→sombre au mot suivant
- `[PAUSE X]` — silence de X secondes
- `[CTA: texte]` — écran final en taille forte
- `*mot*` — emphase (76 px)
- `**MOT**` — forte (110 px)

## Vérification

```bash
python verify.py out/reel.mp4 --timeline out/timeline.json
```

Contrôle : résolution, fps, codec, durée, pas d'images figées, inversion claire→sombre, loudness (-14 LUFS), planche contact.

## Publication TikTok

Le générateur et la publication sont séparés. Pour publier un MP4 déjà généré localement, installez les dépendances optionnelles :

```bash
pip install -r requirements-publish.txt
playwright install chromium
python3 tiktok_publish.py \
  --video out/levelcash_v1_production_final.mp4 \
  --description "Mon nouveau Reel #fyp #business" \
  --cookies-file /chemin/local/cookies.txt
```

Le fichier cookies doit rester local et ignoré par Git. En CI, utilisez plutôt le secret `TIKTOK_SESSIONID` ou `TIKTOK_COOKIES_B64`. Le workflow manuel `.github/workflows/publish-tiktok.yml` télécharge un artifact d'un run précédent et publie uniquement le MP4 choisi, sans cookie dans le dépôt.

## Structure

```
reelforge/
  config.py         # palettes, tailles, durées, chemins
  easing.py         # 4 fonctions d'easing
  flow.py           # machine à états de continuité directionnelle
  script_parser.py  # parse du script annoté
  timeline.py       # chronologie des événements
  elevenlabs_client.py  # voix + alignement ElevenLabs
  pexels_client.py  # recherche + téléchargement Pexels
  sfx.py            # synthèse SFX + bus audio
  audio_mixer.py    # ducking, BGM, mix final
  renderer.py       # compositeur image par image
  make_reel.py      # CLI + orchestration
  verify.py         # vérification automatique
  tests/            # tests unitaires
  example_script.txt
```

## Licence

MIT
