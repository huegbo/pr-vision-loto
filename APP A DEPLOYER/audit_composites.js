#!/usr/bin/env node
// Audit anti-oubli — Forecast Loto 90
// Compare chaque table "source" (un jeu précis) à chaque table "composite" (Multi-Pays,
// Tout Bénin, fusion par jour, etc.) qui est censée contenir les mêmes dates, dans les
// DEUX sens : une date présente dans la source mais absente du composite = oubli de sync ;
// une date présente dans le composite mais absente de la source = table individuelle en retard.
//
// Usage : node audit_composites.js  (depuis le dossier contenant loto-data.js)
// À lancer systématiquement avant de clore toute session de mise à jour de données.

const fs = require('fs');
const path = require('path');

const dataFile = path.join(__dirname, 'loto-data.js');
global.window = { LOTO_DATA: {} };
eval(fs.readFileSync(dataFile, 'utf8'));
const D = window.LOTO_DATA;

function dates(tableName, dateFieldIdx) {
  const raw = D[tableName];
  if (!raw) return null;
  return raw.trim().split('\n').filter(Boolean).map(l => {
    const p = l.split('|');
    return p[dateFieldIdx] + '/' + p[dateFieldIdx + 1];
  });
}

function datesFiltered(tableName, dateFieldIdx, filterFn) {
  const raw = D[tableName];
  if (!raw) return null;
  return raw.trim().split('\n').filter(Boolean).filter(l => filterFn(l.split('|')))
    .map(l => { const p = l.split('|'); return p[dateFieldIdx] + '/' + p[dateFieldIdx + 1]; });
}

let totalIssues = 0;

function compare(label, sourceDates, compositeDates, oneWayOnly) {
  if (sourceDates === null || compositeDates === null) {
    console.log(`  [SKIP] ${label} — table introuvable`);
    return;
  }
  const srcSet = new Set(sourceDates);
  const compSet = new Set(compositeDates);
  const missingInComposite = [...srcSet].filter(d => !compSet.has(d));
  const missingInSource = oneWayOnly ? [] : [...compSet].filter(d => !srcSet.has(d));
  if (missingInComposite.length === 0 && missingInSource.length === 0) {
    console.log(`  [OK]   ${label} (${sourceDates.length} dates source, ${compositeDates.length} composite)`);
  } else {
    totalIssues += missingInComposite.length + missingInSource.length;
    console.log(`  [ECART] ${label}`);
    if (missingInComposite.length) console.log(`          manquant dans le composite: ${missingInComposite.join(', ')}`);
    if (missingInSource.length) console.log(`          manquant dans la table source: ${missingInSource.join(', ')}`);
  }
}

console.log('=== BÉNIN — Digital (D00/D08/D20) ===');
console.log('(RAW_TOUTBENIN et RAW_BENIN_ALL_JEU ne portent pas de code JEU par ligne — plusieurs');
console.log(' jeux partagent la même date, donc un simple diff de dates y donnerait de faux positifs.');
console.log(' Elles ne sont PAS auditées automatiquement ici ; vérifier le total de lignes à la main');
console.log(' si un doute existe (elles doivent grandir d\'une ligne par tirage ajouté, tous jeux confondus).)');
for (const [tbl, code] of [['RAW_DIGITAL_00H', 'D00'], ['RAW_DIGITAL_08H', 'D08'], ['RAW_DIGITAL_20H', 'D20']]) {
  const src = dates(tbl, 1);
  compare(`${tbl} -> RAW_BENIN_ALL (${code})`, src, datesFiltered('RAW_BENIN_ALL', 2, p => p[1] === code));
  compare(`${tbl} -> RAW_DIGITAL_TOUT`, src, dates('RAW_DIGITAL_TOUT', 1), true);
  if (code !== 'D08') compare(`${tbl} -> RAW_DIGITAL_BENIN (D00+D20 seulement)`, src, dates('RAW_DIGITAL_BENIN', 1), true);
}

console.log('\n=== BÉNIN — Star (S11/S14/S18) ===');
const starHourTable = { S11: 'RAW_BJ_H11', S14: 'RAW_BJ_H14', S18: 'RAW_BJ_H18' };
for (const [tbl, code] of [['RAW_BJ_S11', 'S11'], ['RAW_BJ_S14', 'S14'], ['RAW_BJ_S18', 'S18']]) {
  const src = dates(tbl, 1);
  compare(`${tbl} -> RAW_BENIN_ALL (${code})`, src, datesFiltered('RAW_BENIN_ALL', 2, p => p[1] === code));
  compare(`${tbl} -> ${starHourTable[code]}`, src, dates(starHourTable[code], 1), true);
}
// Fusions par jour (RAW_BJ_S_SAM/_DIM/_MER) : S11+S14+S18 combinés (multiset, une entrée
// par tirage, dates dupliquées normales car 2-3 jeux par date) doivent correspondre exactement
// à SAM+DIM+MER combinés (comparaison par COMPTE, pas juste par présence/absence de date).
function multiset(arr) {
  const m = new Map();
  for (const d of arr) m.set(d, (m.get(d) || 0) + 1);
  return m;
}
const starCombined = ['RAW_BJ_S11', 'RAW_BJ_S14', 'RAW_BJ_S18'].flatMap(t => dates(t, 1) || []);
const samDimMerCombined = ['RAW_BJ_S_SAM', 'RAW_BJ_S_DIM', 'RAW_BJ_S_MER'].flatMap(t => dates(t, 1) || []);
const msA = multiset(starCombined);
const msB = multiset(samDimMerCombined);
const allDates = new Set([...msA.keys(), ...msB.keys()]);
let starFusionIssues = [];
for (const d of allDates) {
  const a = msA.get(d) || 0, b = msB.get(d) || 0;
  // one-way seulement : composite > source = historique backfillé directement dans la
  // fusion avant 2023 (connu, pas un bug) ; source > composite = vrai oubli de sync.
  if (a > b) starFusionIssues.push(`${d} (S11/S14/S18: ${a}, SAM+DIM+MER: ${b})`);
}
if (starFusionIssues.length === 0) {
  console.log(`  [OK]   RAW_BJ_S11+S14+S18 -> RAW_BJ_S_SAM+S_DIM+S_MER (${starCombined.length} tirages source, ${samDimMerCombined.length} dans les fusions)`);
} else {
  totalIssues += starFusionIssues.length;
  console.log(`  [ECART] RAW_BJ_S11+S14+S18 -> RAW_BJ_S_SAM+S_DIM+S_MER`);
  console.log(`          écarts de compte: ${starFusionIssues.join(', ')}`);
}

console.log('\n=== TOGO — Matinal (table brute vs tables par jour de semaine) ===');
const matinalAll = dates('RAW_MATINAL', 1);
const dayTables = ['RAW_MATINAL_LUNDI', 'RAW_MATINAL_MARDI', 'RAW_MATINAL_MERCREDI', 'RAW_MATINAL_JEUDI', 'RAW_MATINAL_VENDREDI', 'RAW_MATINAL_SAMEDI'];
let allDayDates = [];
for (const t of dayTables) {
  const d = dates(t, 1);
  if (d) allDayDates = allDayDates.concat(d);
}
compare('RAW_MATINAL -> (somme des 6 tables par jour)', matinalAll, allDayDates);

console.log('\n=== CAMEROUN — jeux individuels vs RAW_CAMEROUN_ALL ===');
const cmGames = [
  ['RAW_CM_CONTINENT', 'CONTINENT'], ['RAW_CM_LIONS', 'LIONS'], ['RAW_CM_LOGONE', 'LOGONE'],
  ['RAW_CM_MBOA', 'MBOA'], ['RAW_CM_MFOUNDI', 'MFOUNDI'], ['RAW_CM_MONT_CAMEROUN', 'MONT_CAMEROUN'],
  ['RAW_CM_MOUNGO', 'MOUNGO'], ['RAW_CM_NOUN', 'NOUN'], ['RAW_CM_SANAGA', 'SANAGA'],
  ['RAW_CM_SUPER4', 'SUPER4'], ['RAW_CM_WOURI', 'WOURI']
  // RAW_CM_DIGITAL est délibérément exclu de RAW_CAMEROUN_ALL (précédent connu, comme le Digital Bénin)
];
for (const [tbl, code] of cmGames) {
  const src = dates(tbl, 1);
  compare(`${tbl} -> RAW_CAMEROUN_ALL (${code})`, src, datesFiltered('RAW_CAMEROUN_ALL', 2, p => p[1] === code));
}

console.log(`\n=== TOTAL: ${totalIssues} écart(s) trouvé(s) ===`);
process.exit(totalIssues > 0 ? 1 : 0);
