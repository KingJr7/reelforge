# OBJECTIF DE QUALITÉ — MOTEUR DE GÉNÉRATION DE SCRIPTS TIKTOK (VIRALIS)

## ⚠️ CE FICHIER EST IMMUABLE

Ce fichier définit la barre de qualité. **Il ne doit jamais être modifié pendant une boucle d'itération**, quelle que soit la difficulté à l'atteindre. Si un script échoue de façon répétée sur un critère, la conclusion est toujours "le moteur de prompt doit s'améliorer", jamais "le critère est trop exigeant, baissons-le". Baisser un critère pour faire passer un script qui échoue est un échec de mission, pas une solution — ça revient à changer la règle du jeu pour gagner.

Un score élevé n'est acceptable que s'il reflète un script réellement solide sur TOUS les axes ci-dessous. Un script brillant sur l'écriture mais qui viole une contrainte dure (durée, message dilué, JSON cassé) doit être noté comme un échec, pas comme "bon avec une réserve".

---

## SECTION A — CONTRAINTES DURES (disqualifiantes, aucune exception)

À vérifier en premier, avant toute évaluation qualitative. Un seul échec ici disqualifie le script, quels que soient ses scores en section B.

**A1. Budget de mots / durée.**
Calcule toi-même le nombre de mots total sur tous les champs parlés (hook + tension + texte de chaque beat de valeur + payoff + cta). Ne fais jamais confiance à un champ auto-déclaré comme `duree_estimee`. Budget = durée_cible_en_secondes × 2.3 mots/seconde. Tolérance maximale : +10% du budget. Au-delà, disqualifié.

**A2. Conformité stricte du schema JSON.**
Tous les champs requis présents, nommés exactement comme spécifié dans le schema du moteur, types corrects. Un champ manquant, renommé, ou un JSON non parsable disqualifie automatiquement le script — c'est ce qui a cassé le pipeline de production par le passé (crash sur un champ `undefined`).

**A3. Un seul message central.**
Tous les beats de la section "valeur" doivent servir une seule révélation ou un seul message central. Test : si tu ne peux pas résumer "ce que cette vidéo apprend" en une seule phrase courte, le script est disqualifié pour dilution. Deux ou trois idées juridiques/informatives différentes casées dans un même script de 30s = échec, même si chaque idée individuelle est bonne.

**A4. Aucune donnée chiffrée ou légale non vérifiée sans signalement.**
Tout montant précis, pourcentage, délai, article de loi ou statistique qui n'est pas explicitement fourni dans le contexte donné par l'utilisateur doit être listé dans `a_verifier`. Une précision chiffrée inventée et présentée avec assurance, sans signalement, disqualifie le script.

**A5. Aucune fuite de vocabulaire de framework.**
Les champs visibles par l'utilisateur final (`legende`, `pourquoi_ca_marche`, `tips`, `cta`) ne doivent jamais contenir de jargon de framework tel que "STEPPS", "pattern interrupt", "social currency", "déclencheur cognitif", "biais de", etc. Reformulation en langage naturel obligatoire.

**A6. Aucun hook dupliqué en structure.**
Si plusieurs scripts sont générés dans la même session de test ou le même pilier de contenu, aucun hook ne doit répéter la même structure syntaxique d'ouverture (5-6 premiers mots) qu'un hook déjà généré. Le squelette rhétorique global d'un pilier PEUT se répéter (voir section E5) — c'est le hook précis qui ne doit jamais être copié.

---

## SECTION B — DIMENSIONS DE QUALITÉ (notées 0 à 10 chacune)

Seulement évaluées si toutes les contraintes dures (section A) sont passées. Chaque dimension doit être notée avec une justification d'une phrase — jamais un chiffre seul sans explication.

**B1. Force du hook** — Active un déclencheur cognitif identifiable (curiosité, pattern interrupt, pertinence personnelle, alerte, excitation chiffrée). Audience nommée avec précision, jamais générique. ≤14 mots ou impact visuel immédiat.
- *Ancre 9-10 :* "tu peux EXIGER qu'on te rembourse la dot ?" — affirmation contre-intuitive vérifiable, question directe.
- *Ancre 2-3 :* "STOP ! Tu veux percer sur TikTok ? J'ai enfin la formule !" — générique, aucune audience nommée, aucun déclencheur clair.

**B2. Tension** — Établit l'enjeu rapidement, sans flottement, sans montée trop lente vers la valeur.

**B3. Concrétude du payoff** — Contient une image, un exemple précis ou une chute, jamais un slogan abstrait.
- *Ancre 9-10 :* "Une vidéo coupée au bon moment peut passer de 500 à 50 000 vues."
- *Ancre 2-3 :* "Fais ça. TikTok poussera tes vidéos. Explose enfin sur la plateforme." — trois généralités sans image.

**B4. Couverture STEPPS** — Au moins 2 des 6 leviers (Social Currency, Triggers, Emotion à haute activation, Public, Practical Value, Stories) réellement présents dans la structure du script, pas juste affirmés dans `pourquoi_ca_marche`.

**B5. Densité et faisabilité visuelle** — Chaque beat a un visuel concret, immédiatement filmable, distinct des autres visuels du même script (pas deux fois le même type de plan).

**B6. Mécanisme de CTA** — Destinataire nommé ("envoie à quelqu'un qui...") et/ou occasion sociale ("ressors ça au prochain repas de famille"), jamais un CTA générique ("like et abonne-toi", "dis-moi ce que t'en penses" seul).

**B7. Spécificité culturelle** — Sonne natif du marché cible (références, rythme, expressions), jamais une traduction mécanique d'un hook ou d'un ton étranger au marché.

**B8. Anti-abstraction** — Sur un sujet vague ou trop large ("comment devenir viral", "comment réussir"), choisit UN angle hyper-spécifique et actionnable plutôt qu'une liste de généralités ou de critères.
- *Ancre 2-3 (échec réel observé) :* un script sur "comment devenir viral" qui liste "watch time, hook, rewatch rate" sans jamais montrer comment obtenir un seul de ces trois.

**B9. Calibrage émotionnel** — Émotion à haute activation adaptée à la catégorie (peur/alerte pour le légal, humour/reconnaissance pour le relatable). Jamais une tristesse plate ou un calme informatif qui freine structurellement le partage.

**B10. Rigueur factuelle** — Précision citable quand elle est fournie ou vérifiable, prudence et reformulation générique quand l'incertitude existe. Ne bascule jamais vers l'excès inverse (perdre toute précision par excès de prudence quand un chiffre était pourtant fourni dans le contexte).

---

## SECTION C — SEUIL DE VALIDATION

**Un script individuel est validé si et seulement si :**
- Toutes les contraintes dures (A1 à A6) passent, sans exception
- ET chaque dimension de qualité (B1 à B10) note ≥ 7/10
- ET la moyenne des 10 dimensions ≥ 8.5/10

**Un cycle de test (lot de 3 ou de 5 scripts) valide le moteur si et seulement si 100% des scripts du lot sont individuellement validés.** Un seul échec dans le lot invalide tout le cycle — pas de moyenne entre scripts.

---

## SECTION D — ANTI-PATTERNS CONNUS (échecs réels déjà observés, à ne jamais reproduire)

1. **Le script méta-creux** : sur un sujet abstrait, lister des critères/généralités au lieu de montrer une technique précise.
2. **La dilution en 3-4 messages** : caser plusieurs points informatifs différents dans un seul script court.
3. **Le chiffre choc halluciné avec assurance** : donner un pourcentage, délai ou montant précis et invérifié sans le signaler.
4. **Le CTA générique de fin** : "like et abonne-toi" sans destinataire ni occasion précise.
5. **Le score gonflé** : un `viral_score` élevé malgré une contrainte dure violée.
6. **Le sur-débit compensatoire** : écrire un script trop long puis suggérer dans les tips d'"accélérer le rythme" pour rattraper un dépassement qui aurait dû être évité à l'écriture.
7. **Le contenu construit autour d'un produit sponsorisé** comme sujet central plutôt qu'en périphérie du CTA.
8. **La métaphore filée en ouverture** : un hook ou une tension qui demande un effort de déchiffrage avant d'être compris.

## SECTION E — PATTERNS DE SUCCÈS CONNUS (à rechercher activement)

1. Risque personnel ignoré + chiffre précis + référence vérifiable citée.
2. CTA combiné : destinataire nommé + incitation à la sauvegarde.
3. Hook par comparaison culturelle déjà chargée émotionnellement ("c'est le nouveau X").
4. Personnage-véhicule pour introduire du vocabulaire technique, révélé au fil d'une progression vécue plutôt que par définition frontale.
5. Squelette rhétorique de pilier répété volontairement (ton, transitions, structure) — SEUL le hook précis et le fait révélé doivent varier, pas l'ADN de la série.

---

## SECTION F — BANQUE DE SUJETS DE TEST

À utiliser pour les cycles de génération. Piocher des sujets différents à chaque cycle ; ne jamais réutiliser les mêmes sujets pour un cycle de test et le cycle de confirmation qui suit. Chaque sujet stresse une règle précise :

1. *"Ton propriétaire n'a pas le droit de te couper l'eau si tu dois du loyer"* — légal/civique, précision factuelle + risque personnel
2. *"Ce vendeur qui te dit 'dernier prix' alors qu'il va encore baisser"* — humour/relatable, calibrage émotionnel + Social Currency
3. *"Comment réussir dans la vie"* — sujet volontairement trop vague, teste directement la règle anti-abstraction (B8)
4. *"Ta société peut racheter ton propre appartement et te donner du cash au passage"* — business/fiscal, densité factuelle + visuel abstrait à concrétiser
5. *"Pourquoi le 50-50 dans un couple peut appauvrir l'un des deux"* — sujet social sensible, teste prudence et absence de sur-généralisation
6. *"3e vidéo d'un pilier 'lois que personne t'explique', sur le droit d'auteur des créateurs de contenu"* — teste le respect du contexte de pilier + squelette répété sans hook dupliqué
7. *"Cette appli que tu utilises tous les jours te fait perdre de l'argent sans que tu le saches"* — sujet à risque de sponsoring déguisé, teste l'anti-pattern D7
8. *"Cette astuce simple pour ne plus jamais rater tes objectifs"* — 2e test de la règle anti-abstraction, angle différent du sujet 3
9. *"Ce client qui annule 10 minutes avant le rendez-vous"* — humour/relatable business, teste Social Currency + mécanisme de tag
10. *"Le montant exact que la sécurité sociale te doit si tu as été mal déclaré par ton employeur"* — légal précis, teste la discipline de vérifiabilité sur un chiffre non fourni dans le contexte

---

## GRILLE DE NOTATION (à copier pour chaque script testé)

```
SCRIPT : [sujet]
── Contraintes dures ──
A1 Durée (mots réels / budget) : ___/___  → PASS / FAIL
A2 Schema JSON conforme : PASS / FAIL
A3 Message unique : PASS / FAIL
A4 Chiffres vérifiés/signalés : PASS / FAIL
A5 Aucune fuite de jargon : PASS / FAIL
A6 Hook non dupliqué : PASS / FAIL
→ Si un seul FAIL ci-dessus : SCRIPT DISQUALIFIÉ, arrêter ici.

── Dimensions de qualité (si toutes contraintes dures PASS) ──
B1 Hook : __/10 — [justification]
B2 Tension : __/10 — [justification]
B3 Payoff : __/10 — [justification]
B4 STEPPS : __/10 — [justification]
B5 Visuels : __/10 — [justification]
B6 CTA : __/10 — [justification]
B7 Culture : __/10 — [justification]
B8 Anti-abstraction : __/10 — [justification]
B9 Émotion : __/10 — [justification]
B10 Rigueur factuelle : __/10 — [justification]

Moyenne : __/10
Validé (moyenne ≥8.5 ET aucune dimension <7) : OUI / NON
```
