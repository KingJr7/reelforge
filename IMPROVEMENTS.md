# Reelforge — plan d'amélioration et suivi

Ce document regroupe les améliorations identifiées pendant l'audit du moteur. Il sert de feuille de route et de journal d'implémentation.

## Légende

- `[x]` implémenté et vérifié
- `[~]` partiellement implémenté ou en cours
- `[ ]` à faire

## État de départ

- Pipeline existant : parser → timeline → audio → rendu image par image → vérification.
- Tests unitaires existants : 35 tests.
- Problèmes prioritaires observés : options `--lufs` et `--invert-at` incomplètes, B-roll vidéo transformé en image fixe, SFX globalement filtrés à 150 Hz, traitement stéréo incomplet, grain recalculé à chaque frame.

## 1. Audio, SFX et mixage

### SFX

- [x] Ajouter un gain par événement SFX.
- [x] Préserver la stéréo des assets SFX lors du panoramique.
- [x] Convertir les assets SFX chargés en 48 kHz.
- [x] Ne plus appliquer le passe-haut 150 Hz aux impacts `land` et `invert`.
- [x] Ajouter des enveloppes d'attaque et de sortie uniformes aux assets SFX importés.
- [ ] Ajouter davantage de variations de pitch, durée et texture aux ticks.
- [ ] Ajouter des couches distinctes pour whoosh, impact, riser et CTA.
- [ ] Ajouter un ducking léger des SFX sous la voix.
- [ ] Remplacer progressivement les sons synthétiques par des assets CC0 documentés.
- [ ] Ajouter une analyse automatique de la bouillie et des événements supprimés.

### Voix, BGM et master

- [x] Ajouter une chaîne voix : passe-haut, de-esser, compression et EQ de présence.
- [~] Normaliser la voix et la BGM par loudness, pas seulement par peak : BGM alignée par RMS, loudness final FFmpeg conservé.
- [ ] Améliorer le ducking BGM avec une enveloppe issue de la voix réelle.
- [x] Ajouter des crossfades lors des boucles BGM.
- [ ] Supprimer la saturation `tanh` globale ou la remplacer par une compression contrôlée.
- [ ] Séparer clairement les bus voix, BGM et SFX.
- [ ] Utiliser une normalisation loudness cohérente avec `--lufs`.
- [ ] Vérifier LUFS, true peak, niveau voix, niveau BGM et clipping dans `verify.py`.
- [ ] Éviter les fichiers temporaires audio à nom fixe.

## 2. Qualité visuelle et motion design

### B-roll et composition

- [x] Lire une séquence de frames pour les vidéos B-roll au lieu d'extraire une seule frame.
- [x] Ajouter un zoom caméra léger par plan.
- [~] Ajouter pan/parallax et synchronisation avec le contenu du plan.
- [ ] Ajouter des recadrages portrait intelligents.
- [ ] Ajouter des compositions `center`, `upper_third`, `lower_third`, `split` et `full_bleed`.
- [ ] Ajouter les marges de sécurité TikTok/Reels.
- [ ] Améliorer le fallback visuel lorsqu'un asset est introuvable.

### Système de motion design réutilisable

- [ ] Créer des tokens de mouvement : durées, easing, offsets et overshoot.
- [ ] Extraire des composants `AnimatedText`, `AnimatedCard`, `AnimatedCTA`, `ImpactFlash` et `BackgroundAccent`.
- [ ] Créer les presets `kinetic_word`, `media_card`, `split_screen`, `impact_reveal` et `cta_final`.
- [ ] Définir trois couches : mouvement principal, mouvement secondaire et ambiance.
- [ ] Synchroniser les événements visuels et SFX avec un événement commun.
- [x] Ajouter plusieurs transitions : `glitch`, `flash`, `wipe`, `zoom`, `blur` et `clean`.
- [ ] Réduire l'utilisation systématique de `ease_out_back`.
- [ ] Ajouter les styles `premium`, `energetic` et `minimal`.
- [~] Accent animé de focus ajouté pour les mots `emphasis`/`strong`; système de presets visuels complets encore à enrichir.
- [ ] Améliorer les contrastes, halos, ombres, accents couleur et textures.
- [ ] Ajouter des contrôles de texte hors écran, contraste et plans figés.

## 3. Performance de génération

- [x] Pré-calculer et réutiliser la texture de grain du background.
- [x] Pré-indexer les éléments actifs par frame pendant le rendu.
- [~] Pré-calculer les frames B-roll et les variantes de sprites carte : caches classic et HTML ajoutés.
- [ ] Réduire les allocations et copies NumPy par frame.
- [ ] Passer les calculs du background en `float32`.
- [ ] Mettre en cache timeline, voix décodée, mix audio, métadonnées et frames B-roll.
- [x] Améliorer le mode preview avec un preset d'encodage dédié.
- [ ] Sélectionner automatiquement l'encodeur CPU/GPU et son preset.
- [ ] Rendre par segments indépendants pour permettre la reprise et le parallélisme.
- [ ] Ajouter un mode de profiling détaillé.
- [ ] Ajouter une gestion robuste des retries API et téléchargements parallèles limités.

## 4. Fiabilité, packaging et CI

- [ ] Rendre `--lufs` réellement configurable dans tout le pipeline.
- [x] Rendre `--invert-at` réellement configurable dans la timeline.
- [ ] Implémenter ou retirer `--auto-broll`.
- [ ] Centraliser l'alignement AssemblyAI dans une fonction testée.
- [ ] Ajouter une validation stricte de timeline avant rendu.
- [ ] Ajouter `pyproject.toml` et des imports de package fiables.
- [~] Ajouter les tests et `verify.py` dans GitHub Actions : tests/compilation/diff ajoutés, verify de rendu restant à ajouter.
- [ ] Utiliser `requirements.txt` dans la CI.
- [ ] Retirer les caches et sorties générées déjà suivis par Git.

## 5. Nouveau moteur HTML frame-driven

- [x] Ajouter un prototype de scène HTML/CSS générative dans `html_motion_renderer.py`.
- [x] Piloter la scène par `frame + fps + totalFrames`, sans horloge CSS ni `Math.random()`.
- [x] Capturer une séquence PNG puis l'encoder en MP4 avec FFmpeg.
- [x] Ajouter un fallback `wkhtmltoimage` lorsque Chromium/Playwright ne peut pas démarrer.
- [x] Définir un motion brief avec beats, couches, safe zones et contraintes dans `html-css-motion-plan.v1.json`.
- [~] Connecter les données de timeline et les timings de voix aux scènes HTML.
- [x] Ajouter des templates de scènes : `hero`, `numbers`, `split`, `cta`, `diagram`, `comparison` et `broll`.
- [x] Intégrer ce moteur comme backend `--engine html` de `make_reel.py`.
- [~] Premier composeur hybride HTML + renderer classique ajouté dans `hybrid_test.py`.
- [ ] Ajouter une bibliothèque de tokens HTML/CSS partagée avec `motion.py`.

## Journal d'implémentation

### Étape 0 — audit initial — terminée

- Analyse des modules audio, SFX, renderer, timeline et CI.
- 35 tests passants avec `PYTHONPATH=.`.
- Identification des principaux défauts listés ci-dessus.

### Étape 1 — qualité SFX et premières optimisations — terminée

- Ajout du `gain_db` par événement SFX.
- Conservation des canaux stéréo des assets SFX.
- Conversion des assets SFX vers 48 kHz.
- Séparation du bus filtré et du bus d'impacts basse fréquence.
- Utilisation réelle de `--lufs` dans le renderer.
- Utilisation réelle de `--invert-at` dans la timeline.
- Grain du background pré-calculé et réutilisé.
- Indexation des mots et cartes actifs par frame.

Vérification attendue : suite de tests complète et rendu démo preview.

Vérification réalisée le 2026-11-03 :

- `PYTHONPATH=. pytest -q` → **35 passed**.
- `python3 -m py_compile *.py` → **OK**.
- `git diff --check` → **OK**.
- Rendu `example_script.txt` en preview → **20,07 s, 603 frames**.
- `verify.py` sur le rendu → **PASS** : résolution, FPS, codec, durée, frames, inversion, loudness et true peak.
- Performance observée sur preview : environ **17 images/s** après indexation du rendu.

### Étape 2 — en cours

- [x] Chaîne de mixage préparée avec traitement vocal léger et ducking SFX contrôlé.
- [~] Chaîne voix/BGM/SFX séparée : bus distincts présents, compression et crossfades BGM encore à affiner.
- [ ] Enveloppes SFX et crossfades BGM.
- [x] Premiers presets motion design réutilisables : `premium`, `energetic`, `minimal`.
- [x] Ajouter des tests de contrat pour les styles motion et le ducking SFX.
- [ ] B-roll vidéo réellement animé.

Vérification intermédiaire :

- `PYTHONPATH=. pytest -q` → **35 passed** après les changements de l'étape 2.
- `python3 -m py_compile *.py` → **OK**.
- `git diff --check` → **OK**.
- Nouvelle option CLI : `--motion-style premium|energetic|minimal`.
- 41 tests passent après ajout des tests motion/audio/transitions.
- Les B-rolls vidéo sont maintenant pré-extraits en séquence de 12 frames et sélectionnés selon le temps de la carte.
- Le zoom carte utilise désormais `CARD_ZOOM_MIN/MAX` au lieu d'être figé à `1.0`.
- Les boucles BGM utilisent un crossfade de 250 ms.
- Nouvelle option CLI : `--transition glitch|flash|clean`.
- Les enveloppes SFX sont couvertes par des tests et les transitions flash/glitch sont bornées.
- Les assets SFX externes reçoivent un fade-in/fade-out de 4 ms pour éviter les clics.
- Les transitions `wipe`, `zoom` et `blur` conservent la taille du canvas et sont couvertes par des tests.
- Rendu réel `out/step3_preview.mp4` avec `--transition flash` → **PASS** dans `verify.py`.
- Loudness du rendu étape 3 : **-13.9 LUFS**, résolution/FPS/durée/codec validés.
- Chaîne voix dynamique validée sur `out/step4_voice_preview.mp4` → **PASS** dans `verify.py`.
- Loudness du rendu étape 4 : **-13.9 LUFS**, sans régression de durée, FPS ou codec.
- Test avec vraie voix `v1.mp3` et script `scripts/levelcash_v1_humain.txt` : `out/levelcash_v1_quality_preview.mp4`.
- Rendu voix réelle → **PASS** dans `verify.py`, loudness **-13.0 LUFS**.
- Pexels hors réseau : le rendu continue avec les assets en cache et des cartes de secours au lieu de planter.
- Rendu `--motion-style premium` → **20,07 s, 603 frames**.
- Motion visible validée avec `--motion-style energetic` dans `out/step5_motion_preview.mp4`.
- Version vraie voix + motion : `out/levelcash_v1_motion_quality_preview.mp4` → **PASS** dans `verify.py`, loudness **-13.0 LUFS**.
- Prototype HTML génératif validé : `out/html_motion_demo.mp4` en 540×960 à 30 FPS.
- Test hybride initial : intro HTML 3 s + segment classique 7 s + voix réelle continue.
- Frame de revue : scène composée par grille, orbite lumineuse, typographie hiérarchisée, carte, numéro et footer animés.
- Prototype enrichi : entrées séquencées, beam traversant, scanline, tag, barres de données et beats cycliques visibles.
- Correction du fallback HTML : injection directe des transforms/opacités par frame, car `wkhtmltoimage` ignorait les query parameters et rendait une scène quasi immobile.
- Mesure de revue : différence RMS entre frames éloignées du prototype dynamique ≈ **46**, contre ≈ **0.6** avant correction.
- `verify.py` sur ce rendu → **PASS**, loudness `-13.9 LUFS`.
- Test hybride généré dans `out/hybrid_test.mp4` : intro HTML motion design **3 s** + renderer classique animé **7 s** + voix réelle continue.
- Validation technique du test hybride : **10 s**, **540×960**, **30 FPS**, vidéo H.264 + audio AAC, sans rupture de durée entre image et son.
- Timeline commune implémentée dans `hybrid_test.py` avec des `SceneSpec` explicites pour chaque moteur.
- Raccord amélioré : transition `xfade` de **350 ms**, avec chevauchement temporel et audio global continu.
- Nouveau rendu final `out/hybrid_test.mp4` régénéré et validé après ce raccord.
- Le prototype hybride lit maintenant `out/timeline.json` pour générer les données éditoriales HTML : premiers mots du script, nombre de mots et durée réelle.
- L'audio du rendu de référence est réutilisé pour conserver voix, SFX et BGM synchronisés sur la timeline globale ; fallback vers le fichier voix si aucune piste source n'est disponible.
- Test validé : `out/hybrid_real_timeline.mp4`, avec contrôle visuel de l'intro et contrôle technique complet.
- Backend unifié ajouté à `make_reel.py` : `--engine classic|html|hybrid`, avec `classic` conservé par défaut.
- Le mode `hybrid` rend maintenant trois scènes selon une timeline commune : intro HTML, corps classic, outro HTML/CTA.
- Les scènes HTML sont générées depuis les données éditoriales de la timeline et les raccords utilisent deux `xfade` de 350 ms avec audio global continu.
- Contrats CLI ajoutés et vérifiés : `PYTHONPATH=. pytest -q` → **47 passed**.
- Smoke test du backend principal : `make_reel.py --engine hybrid --demo --preview` → `out/engine_hybrid_smoke.mp4`.
- `verify.py out/engine_hybrid_smoke.mp4 --timeline out/timeline.json` → **PASS** : durée, audio, inversion, loudness, true peak et absence de frames figées.
- Bibliothèque de templates HTML/CSS ajoutée : `hero`, `numbers`, `split`, `cta`, sélectionnable avec `--html-template`.
- Smoke test réel `html_motion_renderer.py --template numbers` → **PASS**, 540×960, 30 FPS.
- Sélection automatique ajoutée avec `--html-template auto` : chiffres → `numbers`, comparaison → `comparison`, processus → `diagram`, cartes/B-roll → `broll`, CTA → `cta`, fallback → `hero`.
- Contrats de sélection éditoriale ajoutés : `PYTHONPATH=. pytest -q` → **50 passed**.
- Structures dédiées ajoutées aux templates : nœuds/connecteurs pour `diagram`, panneaux AVANT/APRÈS pour `comparison`, cadre média animé pour `broll`.
- Smoke test réel `html_motion_renderer.py --template diagram` → **PASS**, 540×960, 30 FPS.
- Les contenus des structures sont maintenant dérivés de `timeline.json` : mots du hook pour le diagramme, segments de mots pour la comparaison, source B-roll pour le cadre média et CTA réel pour la scène finale.
- Fallbacks éditoriaux conservés si la timeline ne contient pas assez de texte exploitable.
- Analyse sémantique déterministe ajoutée : détection problème/méthode/résultat et contraste avant/après, avec suppression des stopwords et labels limités à 18 caractères.
- Contrats de labels sémantiques ajoutés : `PYTHONPATH=. pytest -q` → **51 passed**.
- Composeur multi-scènes validé sur un smoke test 2 s : vidéo/audio alignés, H.264/AAC, 540×960, 30 FPS.
- Contrôle utilisateur ajouté avec `--scene-plan` et exemple `html-scene-plan.example.json` : l'utilisateur choisit librement les fenêtres contiguës, moteurs et templates ; l'auto-sélection ne force plus le découpage des scènes.
- Le composeur accepte désormais un nombre arbitraire de scènes `html`/`classic` et construit automatiquement la chaîne de transitions `xfade`.
- Chaque scène HTML reçoit maintenant une fenêtre locale de `timeline.json` : mots, cartes, CTA et labels sémantiques sont filtrés sur ses propres bornes.
- Smoke test multiscène avec contenu local : `out/multiscene_local_smoke.mp4`, 2 s, H.264/AAC, 540×960, 30 FPS.
- Contrats de découpe locale ajoutés : `PYTHONPATH=. pytest -q` → **54 passed**.
- Le template `broll` charge maintenant l'asset local réel : image directement en data URI, vidéo convertie en première frame PNG déterministe.
- Smoke test média réel `out/template_broll_media_smoke.mp4` → **PASS**, avec contrôle visuel de l'image injectée dans la composition.
- Les vidéos B-roll HTML utilisent maintenant jusqu'à 12 frames extraites et mises en cache par asset, au lieu d'une seule image fixe.
- Les événements SFX locaux de chaque scène sont maintenant transmis au renderer HTML ; ils déclenchent une pulsation/flash frame-driven autour de l'impact audio.
- Smoke test SFX HTML `out/sfx_motion_smoke.mp4` → **PASS**, 540×960, 30 FPS.
- Chaîne voix améliorée avec EQ de présence légère autour de 1.8–4.2 kHz.
- BGM alignée par RMS avant normalisation de crête pour stabiliser le rapport voix/musique.
- Preview classic accélérée avec preset FFmpeg `veryfast` à 540 px, sans modifier le preset production.
- CI renforcée : tests pytest, compilation Python et `git diff --check` exécutés avant les renders.
- Métriques audio unitaires ajoutées : RMS, peak et crest factor pour préparer le contrôle séparé des bus.
- Suite globale après ce passage : `PYTHONPATH=. pytest -q` → **55 passed**.
- Validation du contrat de plan utilisateur : `PYTHONPATH=. pytest -q` → **53 passed**.

Niveau global actuel : **fondations techniques 2/3 avancées**. Le pipeline historique est stable et le backend `classic|html|hybrid` est maintenant accessible depuis `make_reel.py`. Les templates de scènes, le timing mot-à-mot complet et l'industrialisation restent à implémenter.

### Étape 3 — industrialisation

- Cache par hash des étapes intermédiaires.
- Rendu par segments.
- Profiling et encodeur adaptatif.
- Validation audiovisuelle automatique dans la CI.

