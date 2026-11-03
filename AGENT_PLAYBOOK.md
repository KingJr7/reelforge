# AGENT_PLAYBOOK.md

Copie de la section 11 du prompt de construction — comment produire une vidéo avec reelforge.

## Quand l'utilisateur dit « fais-moi une vidéo sur X »

### 1. Écrire le script

Fichier `scripts/<slug>.txt` :

- Durée visée 30-40 s, **95 à 130 mots** parlés (≈ 3 mots/s avec `speed 1.1`).
- **Phrase d'accroche** dans les 3 premières secondes, avec un `[BROLL]` dès le début (vers 1 s).
- Phrases courtes (6-12 mots). Un `[PAUSE 0.3]` après les phrases importantes.
- Un `[BROLL]` toutes les 4-6 s, durée 1,5-2,5 s, requêtes **en anglais**, concrètes et visuelles (`woman running beach`, pas `success`). Alterne photo et `video`.
- `*emphase*` sur 1 mot clé toutes les 2 phrases, `**MOT**` sur au plus 1 mot dans la vidéo.
- `[INVERT]` : vers le milieu, sur le moment de bascule du discours (« mais », « sauf que »).
- Termine par `[CTA: texte]` si l'utilisateur fournit un site ou un pseudo.

Exemple :

```
Tu savais qu'il existe [BROLL: robot hand typing | 1.8s | medium] une façon de gagner *deux heures* par jour ? [PAUSE 0.3]
Et le plus fou, c'est que tu peux la tester dès **aujourd'hui**. [BROLL: laptop coding | 2.0s | medium video]
[INVERT] Fini la fatigue, fini les tâches répétitives.
[BROLL: sunrise mountains | 2.0s | medium] Tu gagnes du temps, tu respires, tu avances.
[CTA: MONSITE.COM]
```

### 2. Générer

```bash
python make_reel.py --script scripts/<slug>.txt --out out/<slug>.mp4 [--bgm assets/bgm/xxx.mp3]
```

Première passe en `--preview` pour valider vite (la voix est en cache).

### 3. Vérifier

```bash
python verify.py out/<slug>.mp4 --timeline out/timeline.json
```

Regarder `out/contact_sheet.png`. Corriger le script ou les paramètres, relancer. **3 itérations maximum**, puis rendre compte.

### 4. Livrer

Version finale en 1080×1920. Indiquer à l'utilisateur :
- Chemin du fichier MP4
- Durée
- Nombre de B-rolls
- Moment de l'inversion
- Loudness mesurée

### 5. Règles

- Ne pas réutiliser le même B-roll deux fois dans une vidéo.
- Ne pas appeler ElevenLabs si le texte n'a pas changé (le cache s'en charge).
- Jamais de clé API dans les logs ou les fichiers.
