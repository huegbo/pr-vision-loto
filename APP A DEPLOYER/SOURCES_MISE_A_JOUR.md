# Sources des mises à jour en ligne — Forecast Loto 90

Ce fichier recense, pays par pays et jeu par jeu, les sites utilisés pour mettre à jour `loto-data.js`, avec leurs particularités. À consulter EN PREMIER avant toute mise à jour en ligne, et à compléter à chaque nouvelle source trouvée.

## Règles générales (rappel)

- Fichier de données : `loto-data.js` (partagé par `index.html` et le twin `index-v43-fix-noonrush-vagfri-hasm.html`).
- Une mise à jour de données pures (loto-data.js uniquement) NE nécessite PAS de synchro du twin. Seule une modification du `<script>` de `index.html` doit être répercutée dans le twin (vérifier octet-par-octet).
- Dossier de déploiement : `APP A DEPLOYER` (dans `SAUVEGARDE MULTIJEUX 1ER`). Copier `loto-data.js` (et le twin si modifié) là après chaque mise à jour.
- Jamais de `git` exécuté directement : toujours fournir un bloc `git add/commit/push` à copier-coller.
- Toujours vérifier via jsdom après insertion : `loadGame(key)` puis contrôler `idsUnique` et la ligne du haut (`T[0]`), avant de déployer. Utiliser un seul `eval()` concaténant `loto-data.js` + le `<script>` extrait + le code de test (les `let/const` d'un `eval` séparé ne survivent pas d'un appel à l'autre). Stubber `fetch`/`XMLHttpRequest`/`setInterval` pour éviter que le script principal ne bloque sur un appel réseau (IIFE de synchro Supabase en bas du script).
- Format de ligne général : `id|DD/MM|YYYY|n1|n2|n3|n4|n5|total|m1|m2|m3|m4|m5[|mtotal]` — le nombre exact de champs varie par jeu (`hasM`, présence ou non du `mtotal` final) : toujours vérifier le format sur la ligne existante la plus récente avant d'insérer, ne pas supposer.
- Les nombres sont stockés SANS zéro non significatif (`8` pas `08`). Les dates gardent leurs zéros (`03/09`).
- Un écart (gap) d'ID entre deux lignes existe déjà par endroits dans le fichier (ex. Ghana Sunday Special avait un saut 52→51 avec un bond 2025→2022 avant cette session) : ce n'est pas bloquant, l'app tolère les IDs non contigus tant qu'ils sont uniques et ordonnés du plus récent au plus ancien.

---

## Italie — `RAW_IT_*` + `RAW_CAGLIARI`

**Source : estrazionedellotto.it** (page d'accueil = dernier tirage ; `/ultime-estrazioni-lotto` = historique 60 jours, largement suffisant pour rattraper).
⚠️ `lottomatica.it` / `lottomaticaitalia.it` = bloqués ("Access Denied", protection Akamai) — ne pas réessayer.

- 10 ruote : Bari, Cagliari, Firenze, Genova, Milano, Napoli, Palermo, Roma, Torino, Venezia + Nazionale → variables `RAW_IT_BARI`, `RAW_IT_FIRENZE`, `RAW_IT_GENOVA`, `RAW_IT_MILANO`, `RAW_IT_NAPOLI`, `RAW_IT_PALERMO`, `RAW_IT_ROMA`, `RAW_IT_TORINO`, `RAW_IT_VENEZIA`, `RAW_IT_NAZIONALE`.
  ⚠️ **PIÈGE** : Cagliari est stockée sous `RAW_CAGLIARI` (SANS le préfixe `IT_`) — un grep sur `RAW_IT_` seul l'oublie (déjà arrivé une fois, corrigé le 04/09/2026). Toujours vérifier les 11 tables une par une, pas seulement celles qui matchent `RAW_IT_*`.
- SuperEnalotto → `RAW_IT_SUPERENALOTTO` (format n6 : 6 numéros + total + jolly/superstar `x:[j,s]`). Piège vérif : `parseLines()` lit l'état global `GAME.n6`, donc toujours faire `loadGame('it_superenalotto')` avant de lire `T`, jamais `gameData()` seul.
- Tirages Lotto : mardi / jeudi / vendredi / samedi (~20h). Extraction efficace via regex JS sur `document.body.innerText` (page `/ultime-estrazioni-lotto`), motif `Estrazione n\. (\d+)\n(\d\d)\/(\d\d)\/(\d\d\d\d)\n\nBari\n...` répété par ruota.

---

## Nigeria — `RAW_NG_*`, `RAW_ENUGU`

**Source : babaijeburesults.ng**

- 7 jeux (National, Bonanza, Fortune, Midweek, MSP, Aseda, Lucky) sont des rediffusions de tirages ghanéens et sont **volontairement exclus** de `RAW_NG_*` (comment dans `index.html` ~ligne 394) pour éviter les doublons.
- Piège clé de jeu : `ng_enugu` (pas `enugu`) pour `RAW_ENUGU`.

---

## Ghana — jeux « core » (5/90 quotidiens, NOONRUSH, VAG jour-par-jour, DAYWA)

**Source : ghanayello.com**, page `/lottery/results/history` (filtre par jeu + par mois, "Last 30 draws" par défaut = largement suffisant).
Alternative de secours : `ghanawebsolutions.com` (page d'accueil = tableau "Latest Winning Numbers") — utile si ghanayello est indisponible, mais moins complet (pas de machine numbers sur les tout derniers tirages parfois).
⚠️ Piège d'accès : `navigate` seul peut échouer ("navigation denied") sur ces domaines — utiliser `preview_start` avec l'URL cible directement, plus fiable pour ouvrir une session fraîche.

- Monday Special → `gh_g14`, Lucky Tuesday → `gh_g12`, Mid Week → `gh_g13`, Fortune Thursday → `gh_g8`, Friday Bonanza → `gh_g9`, National Weekly → `national` (`RAW_NATIONAL`), Sunday Aseda → `gh_g19`.
- NOONRUSH (par jour) → Monday `gh_g15`, Tuesday `gh_g25`, Wednesday `gh_g35`, Thursday `gh_g24`, Friday `gh_g10`, Saturday `gh_g20`.
- VAG (par jour) → Monday `gh_g28`, Tuesday `gh_g31`, Wednesday `gh_g32`, Thursday `gh_g30`, Friday `gh_g27`, Saturday `gh_g29`. (VAG générique/East/West = `gh_g26`/`gh_g33`/`gh_g34`, non couverts par cette source — voir section "non trouvés" plus bas.)
- DAYWA (un seul tirage quotidien, tous les jours) → `gh_g7` (`RAW_GH_G7`, pas de machine numbers stockés — cohérent avec le site qui affiche "-" pour DAYWA).

---

## Ghana — famille GH ALPHALOTTO (Precise/Alpha/Delta/Omega/Excel/Prime/Kenstar/Express/One)

**Source : lotteryspy.com**, URL pattern `https://lotteryspy.com/chart/page/gh.al.<jeu>.lotto` :
`gh.al.alpha.lotto`, `gh.al.delta.lotto`, `gh.al.omega.lotto`, `gh.al.excel.lotto`, `gh.al.prime.lotto`, `gh.al.kenstar.lotto`, `gh.al.precise.lotto`, `gh.al.express.lotto` (Alpha Express, TOUS les jours mélangés dans une seule table), `gh.al.one.lotto` (Alpha One, idem).

- Mapping clé de jeu : `precise` (dimanche), `alpha` (lundi), `delta` (mardi), `omega` (mercredi), `excel` (jeudi), `prime` (vendredi), `kenstar` (samedi).
- `alpha_express_mon..sun` et `alpha_one_mon..sun` : la page site est UNIQUE par famille (Express / One) et mélange tous les jours — il faut regarder la date de chaque ligne, en déduire le jour de la semaine, puis router vers la bonne clé (`alpha_express_wed`, etc.).
- Extraction efficace : `document.body.innerText`, slice entre `'CURRENT RESULTS DISPLAYED'` et `'DATE CHART'`, regex `/Raffle\n(\d+)\n(\d{4}-\d\d-\d\d).../g`. La page par défaut montre déjà les ~20 derniers tirages (pas besoin de filtre).
- Site officiel de référence (pour vérification croisée, PAS pour extraction automatisée) : **myalphaonline.com** — app Blazor Server très fragile à piloter par automatisation (calendrier custom, pas d'`<input type=date>` natif, le défilement de la liste d'années casse l'affichage). Bon pour un contrôle visuel ponctuel, à éviter pour du scraping.
- Recherche par événement/date sur lotteryspy.com (`from_event`/`to_event`, `from_year`/`to_year`) semble verrouillée derrière un compte (bouton "SUBMIT EVENT/DATE SEARCH" ne déclenche rien sans login) — **ne pas créer de compte** pour la débloquer. La fenêtre par défaut (~20 lignes) est la seule exploitable sans compte.

---

## Ghana — « famille 2 » (Golden Souvenir, Sunday Special, Obiri, Sports, International, VAG West, Old Soldier, Pioneer, Home Lucky, Super 6, "5-39 DIRECT")

**Source partielle : lotteryspy.com**, URL pattern `https://lotteryspy.com/chart/page/gh.<jeu>.lotto` (pas de préfixe `al.`) :
`gh.golden.souvenir.raffle`, `gh.obiri.special.raffle`, `gh.sports.lotto`, `gh.sunday.special.lotto`, `gh.international.lotto`, `gh.v.west.special.raffle` (= VAG West), `gh.centenary.lotto`, `gh.diamond.lotto`, `gh.from.home.ape.lotto`, `gh.vision.2000.lotto`.

État au 04/09/2026 (à re-vérifier avant toute nouvelle tentative) :
- **Golden Souvenir** (`gh_g11`) et **Sunday Special** (`gh_g22`) : rattrapés partiellement (juin/mai 2025 → février 2026). Le site lui-même semble s'arrêter de suivre ces jeux vers mars 2026 (event max proche de la dernière ligne visible) — probablement proche de la limite réelle de données disponibles.
- **Obiri** (`gh_g16`) et **Sports** (`gh_g21`) : le site est MOINS à jour que notre appli (numérotation d'événements différente, données qui s'arrêtent avant nos propres dernières entrées) — rien à en tirer, ne pas retenter sans nouvelle source.
- **Non trouvés du tout** : Old Soldier (`gh_g17`), Pioneer (`gh_g18`), Home Lucky (`gh_home_lucky`), GH International (`gh_international` — distinct de "International Lotto" du site, à vérifier si c'est le même jeu), Super 6 (`gh_g23`), VAG générique (`gh_g26`) et VAG East (`gh_g33`), et toute la famille « 5-39 DIRECT » (`gh_g1`..`gh_g6`, un jeu à 5 numéros tirés sur 39, distinct du DAYWA malgré la même plage). Probablement des jeux discontinués ou nécessitant une source encore différente — à re-chercher si besoin, ou accepter qu'ils restent figés.

---

## Côte d'Ivoire — `RAW_CI_*` (LONACI / Loto Bonheur)

**Source : lotobonheur.ci** (`/resultats`) — site officiel affilié LONACI.
API JSON directement exploitable (bien plus rapide que parser le HTML) : `GET https://lotobonheur.ci/api/results?monthYear=<mois%20année>&drawType=Tous%20les%20tirages`
— `monthYear` doit reprendre exactement une valeur de la liste `monthYears` renvoyée par l'API (ex. `"août 2026"`, accent inclus, URL-encodé) ; sans paramètre, l'API renvoie la semaine en cours par défaut.
Réponse : `drawsResultsWeekly[].drawResultsDaily[]` = un objet par jour, avec `date` (ex. `"jeudi 03/09"`, sans année — la déduire du `monthYear` demandé) et `drawResults.nightDraws[]` + `drawResults.standardDraws[]`, chaque tirage ayant `drawName`, `winningNumbers` (`"80 - 73 - 32 - 24 - 33"`) et `machineNumbers` (`". - . - . - . - ."` si absent). Filtrer les entrées `drawName==='-'`.

- Mapping direct nom-du-site → clé de jeu : Reveil→`ci_reveil`, Etoile→`ci_etoile`, Akwaba→`ci_akwaba`, Monday Special→`ci_monday_special` (RAW_CI_MONDAY_SPECIAL, sans M), La Matinale→`ci_matinale`, Emergence→`ci_emergence`, Sika→`ci_sika`, Lucky Tuesday→`ci_lucky_tuesday` (sans M), Premiere Heure→`ci_premiere_heure`, Fortune→`ci_fortune`, Baraka→`ci_baraka`, Midweek→`ci_midweek` (sans M), Kado→`ci_kado`, Privilege→`ci_privilege`, Monni→`ci_monni`, Fortune Thursday→`ci_fortune_thursday` (sans M), Cash→`ci_cash`, Solution→`ci_solution`, Wari→`ci_wari`, Friday Bonanza→`ci_friday_bonanza` (sans M), Soutra→`ci_soutra`, Diamant→`ci_diamant`, Moaye→`ci_moaye`, National→`ci_national2` (RAW_CI_NATIONAL2, sans M), Benediction→`ci_benediction`, Prestige→`ci_prestige`, Awale→`ci_awale`, Espoir→`ci_espoir`, Day Off→`ci_dayoff`, Digital 21h→`ci_digital21h`, Digital Reveil 7h→`ci_reveil_07h`, Digital 23h→`ci_digital23h`, Special Weekend 1h→`ci_sw1h`, Special Weekend 3h→`ci_sw3h`, Digital Reveil 8h→`ci_reveil_08h`, Digital 22h→`ci_digital22h`, Afterwork→`ci_afterwork`.
- Monday Special/Lucky Tuesday/Midweek/Fortune Thursday/Friday Bonanza = rediffusions des tirages ghanéens (mêmes numéros que Ghana), mais contrairement au Nigeria, la CI ne les exclut PAS — ils sont stockés normalement.
- Cadences hebdomadaires par jeu (1 tirage/semaine, sauf Digital* et Afterwork qui sont quotidiens) : Reveil/Etoile/Akwaba/Monday Special = lundi. La Matinale/Emergence/Sika/Lucky Tuesday = mardi. Premiere Heure/Fortune/Baraka/Midweek = mercredi. Kado/Privilege/Monni/Fortune Thursday = jeudi. Cash/Solution/Wari/Friday Bonanza = vendredi. Soutra/Diamant/Moaye/National = samedi. Benediction/Prestige/Awale/Espoir = dimanche. Special Weekend 1h/3h = samedi ET dimanche (deux tirages distincts par week-end, bien vérifier qu'aucun des deux n'est déjà présent avant d'insérer). Avant de chercher du nouveau, vérifier la cadence : si le prochain jour de tirage n'est pas encore passé, il n'y a simplement rien de neuf à ajouter.
- **Day Off** : tirage rarissime/occasionnel (une seule occurrence vue sur juillet-septembre 2026, le 03/07). Vérifier son absence dans les mois récents avant de conclure à un retard — c'est normal qu'il n'y ait rien de neuf la plupart du temps.
- **Nuit Etoilee** (`ci_nuit_etoilee`, figée depuis 16/03/2022) : n'apparaît PAS dans la liste `drawTypes` de ce site — jeu très probablement discontinué, à ne plus chercher sauf nouvelle piste.

---

## Bénin / Cameroun / Togo / Burkina Faso

Sources non documentées lors de cette session (mises à jour faites lors de sessions antérieures). Conventions connues à respecter :
- Bénin : codes jour français (L, MA, ME, J, V, S, D). Jeu "Digital 00H" : la date stockée dans l'appli est un jour APRÈS la date affichée littéralement sur le site source (convention propre à ce jeu).
- Cameroun : codes jour anglais 2 lettres (MO, TU, WE, TH, FR, SA, SU). **Correction (05/09/2026)** : contrairement à une note antérieure erronée, les 2 "xtras" bonus des roues NE sont PAS exclus — ils sont bien stockés, dans un champ `x` séparé (`r.x=[+p[14],+p[15]]` dans `parseLines()`), lisible dans `loto-data.js` aux positions 15-16 de chaque ligne (après les 5 "premiers" en positions 10-14).
- **Cameroun — sources confirmées (05/09/2026)** : compte X **@Hervevilla9** ("PREMIERBET CAMEROUN RESULTATS LOTO 5/90") — **accessible directement via le navigateur intégré, SANS connexion** (`preview_start` sur `https://x.com/Hervevilla9`, puis `get_page_text`) : publie les résultats des 10 roues + Super4, souvent en 2 posts séparés par jeu ("5 derniers" puis "7 premiers", parfois à des heures différentes — vérifier les deux avant de considérer un jeu incomplet). Limite : le défilement infini est bloqué sans compte (~5 posts visibles), donc utile seulement pour les tout derniers tirages, pas pour un rattrapage historique.
  Page Facebook **"Premierbet resultats loto 5/90"** (alias "PREMIERBET🇨🇲 LOTO_RESULTAT & FOOTBALL PRONOSTICS") : accessible aussi sans connexion, mais **peu exploitable via la recherche de groupe** — la recherche par mots-clés dans le groupe "Résultats Loto Cameroun" (8,5K membres) ne remonte que d'anciennes publications/pronostics, pas le récap du jour même.
  **MISE À JOUR (06/09/2026)** : cette même page ("PREMIERBET🇨🇲 LOTO_RESULTA...", posts relayés par ex. par "Alicia Mefo") publie en réalité un **visuel propre et fiable**, "5/90 RÉSULTATS : DD/MM/YY", groupant les 10 roues par heure (8h00 Moungo, 9h30 Wouri, 11h00 Mfoundi, 12h30 Logone, 14h00 Mont Cameroun, 15h30 Noun, 17h00 Sanaga, 18h30 Lions, 20h00 Mboa, 21h00 Continent) avec pour chaque roue "7 PREMIERS" (5 numéros + 2 XTRAS cerclés) et "5 DERNIERS" (machine). Les roues pas encore tirées à l'heure de la capture affichent des ronds vides — à ne PAS insérer, repasser plus tard. **Ce visuel-là est directement lisible et fiable** (ce n'était pas la même image que la fois précédente jugée "OCR cassé") ; à privilégier si l'utilisateur peut le capturer/partager, l'X @Hervevilla9 restant l'option si on doit chercher sans capture fournie.
  Dans les deux cas, si un jeu n'a que ses 5 "derniers" numéros disponibles (pas les 7 premiers/xtras), insérer uniquement ces 5 valeurs (n1-5, sans m ni x) plutôt que d'inventer — et repasser mettre à jour la même ligne dès que le 2e post (7 premiers) apparaît, sans créer une nouvelle ligne.
- **Togo — format des jeux (confirmé 06/09/2026)** : tous les jeux Togo ont 5 numéros (n1-5 seulement, pas de machine), **SAUF** les MATINAL (Lundi/Mardi/Mercredi/Jeudi/Vendredi/Samedi — pas de Matinal le dimanche) et DETENTE (le dimanche 16h), qui ont 10 numéros (5 "N" + 5 "M", `hasM:true`). Vérifier ce format avant d'insérer un nouveau tirage Togo pour ne pas se tromper de nombre de champs.
- À compléter avec les URLs sources dès qu'elles seront réutilisées.

---

## ⚠️ Tables COMPOSITES à resynchroniser manuellement (checklist obligatoire à chaque mise à jour)

Plusieurs pays ont, EN PLUS des tables individuelles par jeu (`RAW_GH_G8`, `RAW_CM_LOGONE`, `RAW_DIGITAL_00H`, etc.), une ou plusieurs tables **composites** qui dupliquent ces mêmes données pour alimenter une "vue dédiée" (filtre Jour/Jeu, comparaison multi-jeux). Ces composites sont des **instantanés statiques indépendants** : mettre à jour la table individuelle NE met PAS à jour le composite automatiquement (sauf exceptions listées) — oubli fréquent, découvert le 05/09/2026 sur plusieurs pays d'affilée. **Toujours vérifier/synchroniser ces composites après toute mise à jour d'un jeu individuel qui en fait partie.**

### Ghana — `RAW_GHANA_ALL`
- **Cas particulier IMPORTANT** : la famille Alpha Lotto (precise/alpha/delta/omega/excel/prime/kenstar/express×7/one×7), **G21 (Sports)** et **HOMELUCKY (Home Lucky)** sont lus **dynamiquement** depuis leurs tables individuelles à chaque rendu (`parseGhanaAll()`, ligne ~783 de `index.html`) — **PAS besoin de les resynchroniser**, ils sont toujours à jour automatiquement.
- **Tous les autres jeux "core"** (G1-G20, G22-G35, NATL — Fortune Thursday, Daywa, Golden Souvenir, Sunday Special, Mid Week, Lucky Tuesday, les NOON RUSH, les VAG, etc.) dépendent du blob statique `RAW_GHANA_ALL` : **à resynchroniser à la main** après chaque mise à jour de l'un de ces jeux.
- Format d'une ligne composite : `JOUR|CODE_JEU|DD/MM|YYYY|n1|n2|n3|n4|n5|m1|m2|m3|m4|m5` (m vides si pas de machine numbers). Jour = code 2 lettres (`MO,TU,WE,TH,FR,SA,SU`), déductible de la date via `new Date(y,m-1,d).getDay()`.
- Le 05/09/2026 : 1889 lignes manquantes détectées et rattrapées d'un coup (tout l'historique de 11 jeux n'avait jamais été synchronisé) — voir tableau d'historique plus bas.

### Cameroun — `RAW_CAMEROUN_ALL`
- Composite ENTIÈREMENT statique (aucune lecture dynamique) — les 11 jeux (Moungo, Wouri, Mfoundi, Logone, Mont Cameroun, Noun, Sanaga, Lions, Mboa, Continent, Super4) doivent TOUJOURS être ajoutés ici en plus de leur table individuelle.
- Format : `JOUR|CODE_JEU|DD/MM|YYYY|n1|n2|n3|n4|n5|m1|m2|m3|m4|m5` — reprend seulement les 5 "premiers" (m1-m5), PAS les xtras (contrairement aux tables individuelles qui les stockent en position 15-16, cf. section Cameroun ci-dessus). CODE_JEU = nom en majuscules (`MOUNGO`, `MONT_CAMEROUN`, `SUPER4`, etc.), Super4 n'a que 4 numéros donc n5 est mis à `0` (padding).

### Bénin — PLUSIEURS composites indépendants, à vérifier un par un
- `RAW_BENIN_ALL` — **découvert le 06/09/2026, jusque-là oublié dans toutes les mises à jour Bénin de cette session** (cause du "je dois répéter ça partout" signalé par l'utilisateur). Composite ENTIÈREMENT statique couvrant SEULEMENT 9 jeux (`BENIN_JEU_ORDER` : D00, D08, D20, F11, F14, F18, S11, S14, S18 — pas Bénédiction, pas les Matinal/Détente Togo, etc.). Format : `JOUR|CODE_JEU|DD/MM|YYYY|n1-5|total|m1-5 (vides si pas de machine)` — jour = code français 1-2 lettres (L,MA,ME,J,V,S,D). Trié par date décroissante, puis à l'intérieur d'une même date par heure décroissante (D20 20h → S18/F18 18h → S14/F14 14h → S11/F11 11h → D08 8h → D00 00h). Seuls F14 et S14 ont des numéros machine (m1-5) ; les 7 autres n'en ont pas.
- "STAR DIMANCHE" (`RAW_BJ_S_DIM`, jeu affiché séparément dans l'appli) n'est **pas un jeu à part** : ses valeurs sont systématiquement identiques à celles de STAR 18H (`RAW_BJ_S18`) le dimanche — vérifié sur 3 semaines consécutives (16/08, 23/08, 30/08). Donc pour la mettre à jour, copier simplement la ligne du dimanche de STAR 18H, pas besoin d'une source séparée. Elle n'alimente ni `RAW_TOUTBENIN` ni `RAW_BENIN_ALL_JEU` (S18 y est déjà présent sous son propre nom).
- `RAW_DIGITAL_BENIN` : fusionne UNIQUEMENT Digital 00H + Digital 08H + Digital 20H, dans l'ordre chronologique réel (00h du jour J vient après 20h du jour J-1). Format 9 champs (`id|d|y|n1-5|total`), IDs séquentiels propres (pas de code jour).
- `RAW_DIGITAL_TOUT` (jeu "TOUT DIGITAL") : fusionne EXACTEMENT les 3 mêmes jeux (00H/08H/20H) mais dans une table SÉPARÉE avec sa propre numérotation — doublon fonctionnel de `RAW_DIGITAL_BENIN`, à synchroniser en parallèle, pas automatiquement lié.
- `RAW_TOUTBENIN` (jeu "TOUT BENIN PLUS DIGITAL") : le plus gros composite, fusionne ~17 jeux individuels (Digital 00h/08h/20h + Fortune 11h/14h/18h + Star 11h/14h/18h + les variantes par jour de semaine Fortune/Star Lundi..Dimanche). **Ne PAS inclure** `bj_h11`/`bj_h14`/`bj_h18` ("TOUT 11H/14H/18H") comme sources — ce sont eux-mêmes des composites Fortune+Star, les inclure créerait des doublons.
- `RAW_BENIN_ALL_JEU` ("ALL BENIN officiel") : **confirmé composite statique lui aussi (06/09/2026)** — même mécanique que les autres, à resynchroniser après chaque mise à jour d'un des ~17 jeux Bénin. Astuce rapide de reconciliation : comparer ses signatures à celles de `RAW_TOUTBENIN` (déjà à jour) plutôt que de ressaisir depuis chaque jeu individuel — les deux composites couvrent normalement le même périmètre.
- Méthode de reconciliation utilisée (réutilisable) : pour chaque jeu source, construire une "signature" = tous les champs après `id|date|year` (ex. `n1|n2|n3|n4|n5|total` ou avec m1-5 en plus), comparer à l'ensemble des signatures déjà présentes dans le composite, ajouter les lignes manquantes. Un script Node rapide suffit (voir historique de session du 05/09/2026).

### En pratique
Après toute mise à jour d'un jeu individuel Ghana/Cameroun/Bénin, se demander : "ce jeu fait-il partie d'un composite ci-dessus (hors cas dynamiques Ghana) ?" Si oui, répéter la même insertion dans le composite avant de considérer la mise à jour terminée.

---

## Historique des mises à jour effectuées

| Date session | Périmètre | Source | Résultat |
|---|---|---|---|
| 04/09/2026 | IT Torino (historique 2006) | Fichier Excel fourni par l'utilisateur | 156 lignes ajoutées (id 7537-7692) |
| 04/09/2026 | Italie 10 ruote + Nazionale + SuperEnalotto | estrazionedellotto.it | +6 tirages chacune, jusqu'au 03/09/2026 |
| 04/09/2026 | Nigeria (15 tables + Enugu) | babaijeburesults.ng | +1 à +2 tirages chacune |
| 04/09/2026 | Ghana core (9 tables : Fortune Thu, Thu Noon Rush, Mid Week, Wed Noon Rush, Lucky Tue, Tue Noon Rush, VAG Thu, VAG Wed, Daywa) | ghanayello.com | +1 à +3 tirages chacune |
| 04/09/2026 | Ghana famille Alpha (12 tables) | lotteryspy.com | +1 tirage chacune, jusqu'au 01-03/09/2026 |
| 04/09/2026 | Ghana Golden Souvenir + Sunday Special | lotteryspy.com | +20 tirages chacune (rattrapage partiel juin/mai 2025 → février 2026) |
| 04/09/2026 | IT Cagliari (oubliée lors du passage Italie) | estrazionedellotto.it | +6 tirages, jusqu'au 03/09/2026 |
| 04/09/2026 | Côte d'Ivoire (Digital Reveil 7h, Monday Special) | lotobonheur.ci (API JSON) | +1 tirage chacune ; le reste des ~35 jeux CI était déjà à jour (cadences hebdo vérifiées une à une) |
| 05/09/2026 | Découverte + resynchro composites Ghana/Cameroun/Bénin (voir section dédiée ci-dessus) | Reconciliation interne (signatures) depuis les tables individuelles déjà à jour | Ghana `RAW_GHANA_ALL` : +1889 lignes (11 jeux jamais synchronisés). Cameroun `RAW_CAMEROUN_ALL` : +11 lignes (04/09). Bénin `RAW_DIGITAL_TOUT` : +10 lignes. Bénin `RAW_TOUTBENIN` : +4 lignes récentes (04-05/09) + 8 lignes de rattrapage plus anciennes (22/08-01/09), avec renumérotation complète de la table (IDs contigus 1-5592) pour respecter l'ordre chronologique |
| 06/09/2026 | Cameroun 8 roues (Moungo, Wouri, Mfoundi, Logone, Mont Cameroun, Noun, Sanaga, Lions) — Mboa et Continent pas encore tirées à l'heure de la capture, non insérées | Capture d'écran fournie par l'utilisateur, page Facebook "PREMIERBET🇨🇲 LOTO_RESULTA..." (voir note source ci-dessus) | +1 tirage chacune des 8 tables individuelles + 8 lignes synchronisées dans `RAW_CAMEROUN_ALL` (code jour `SU`=Dimanche) |
