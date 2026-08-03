import streamlit as st
import pandas as pd
import numpy as np
import json
import os
from pathlib import Path
from core.comparator import comparer_deux_lotos
from core.picker import generer_pronostics, detecter_bankers
from core.classification import CORRESPONDANCE, LABELS, get_classifications

st.set_page_config(page_title="Loto Forecast Pro", layout="wide")
st.title("🔮 Loto Forecast Pro - 34 Lotos (LOTO MULTI JEUX intégré)")

# ═══ CACHE JSON LOCAL ═══
CACHE_DIR = Path.home() / ".loto_forecast_cache"
CACHE_DIR.mkdir(exist_ok=True)

def save_cache(loto_name, data):
    """Sauvegarde les données en JSON"""
    cache_file = CACHE_DIR / f"{loto_name}.json"
    with open(cache_file, 'w') as f:
        json.dump(data, f)

def load_cache(loto_name):
    """Charge les données du cache JSON"""
    cache_file = CACHE_DIR / f"{loto_name}.json"
    if cache_file.exists():
        with open(cache_file, 'r') as f:
            return json.load(f)
    return None

def list_cached_lotos():
    """Liste les lotos en cache"""
    return [f.stem for f in CACHE_DIR.glob("*.json")]

# ═══ DONNÉES INTÉGRÉES DE LOTO MULTI JEUX (auto-seed, une seule fois) ═══
LOTO_DATA_DIR = Path(__file__).parent / "loto_data"

def seed_bundled_lotos():
    """Pré-remplit le cache avec les tirages de LOTO MULTI JEUX pour les lotos
    absents du cache. N'écrase jamais un loto déjà présent (upload manuel ou
    ancien cache)."""
    meta_path = LOTO_DATA_DIR / "_meta.json"
    if not meta_path.exists():
        return
    try:
        with open(meta_path, 'r', encoding='utf-8') as f:
            bundled = json.load(f)
    except Exception:
        return
    for entry in bundled:
        nom = entry["name"]
        cache_file = CACHE_DIR / f"{nom}.json"
        if cache_file.exists():
            continue
        data_file = LOTO_DATA_DIR / f"{nom}.json"
        if not data_file.exists():
            continue
        try:
            with open(data_file, 'r', encoding='utf-8') as f:
                tirages = json.load(f)
            save_cache(nom, tirages)
            meta_file = CACHE_DIR / f"_{nom}_meta.json"
            if not meta_file.exists():
                with open(meta_file, 'w', encoding='utf-8') as mf:
                    json.dump({"boules": 10 if entry.get("hasM") else 5}, mf)
        except Exception:
            pass

seed_bundled_lotos()

# ═══ PRÉDICTIONS SAUVEGARDÉES (persistées sur disque, comme Oracle du Loto) ═══
PRED_FILE = CACHE_DIR / "_predictions.json"

def load_predictions():
    if PRED_FILE.exists():
        try:
            with open(PRED_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_predictions(preds):
    with open(PRED_FILE, 'w') as f:
        json.dump(preds, f)

def add_prediction(loto, strategie, numbers):
    import datetime
    preds = load_predictions()
    preds.setdefault(loto, [])
    preds[loto].append({
        "date": datetime.date.today().isoformat(),
        "strategie": strategie,
        "numbers": list(numbers),
    })
    save_predictions(preds)

def delete_prediction(loto, idx):
    preds = load_predictions()
    if loto in preds and 0 <= idx < len(preds[loto]):
        preds[loto].pop(idx)
        save_predictions(preds)

LOTOS_CONFIG = {
    "9h00": ["MATINAL"],
    "13h00": ["DIAMANT", "CASH", "BENZ", "MILLION", "KADOO", "SAM"],
    "18h00": ["GOLD", "BOOM", "PRESTIGE", "SUPER", "KING", "BINGO"],
    "🌅 Matinales (par jour)": ["MATINAL LUNDI", "MATINAL MARDI", "MATINAL MERCREDI", "MATINAL JEUDI", "MATINAL VENDREDI", "MATINAL SAMEDI"],
    "🎯 Autres jeux TOGO": ["MID-WEEK", "SUNDAY ASEDA", "PRECISE", "ALPHA LOTTO"],
    "🇧🇯 Bénin (Tout Bénin)": ["TOUT BENIN", "BENIN LUNDI", "BENIN MARDI", "BENIN MERCREDI", "BENIN JEUDI", "BENIN VENDREDI", "BENIN SAMEDI", "BENIN DIMANCHE"],
    "🌍 International": ["CAGLIARI", "MALTA"],
    "🌍 National": ["NATIONAL WEEK"]
}

st.sidebar.header("📁 Mes Lotos")

with st.sidebar.expander("📅 Horaire LONATO"):
    for heure, lotos in LOTOS_CONFIG.items():
        st.write(f"**{heure}** : {', '.join(lotos)}")

# Liste des 13 lotos LONATO par défaut
all_lotos = []
for heure_list in LOTOS_CONFIG.values():
    all_lotos.extend(heure_list)

# ═══ ➕ AJOUTER UN NOUVEAU LOTO (scalable 40+) ═══
with st.sidebar.expander("➕ Ajouter un loto"):
    new_name = st.text_input("Nom du loto", placeholder="Ex: ALPHA LOTTO", key="new_loto_name")
    new_boules = st.selectbox("Nombre de boules", [5, 10], key="new_loto_boules")
    new_file = st.file_uploader("Fichier Excel", type=["xlsx", "xls"], key="new_loto_file")
    if st.button("✅ Ajouter ce loto", key="new_loto_btn", use_container_width=True):
        if new_name.strip() and new_file:
            nom = new_name.strip().upper()
            # sauvegarder la config du loto
            meta = {"boules": int(new_boules)}
            with open(CACHE_DIR / f"_{nom}_meta.json", 'w') as f:
                json.dump(meta, f)
            st.session_state[f"pending_new_loto"] = (nom, new_file)
            st.success(f"✅ {nom} ajouté ! ({new_boules} boules)")
        else:
            st.error("Nom + fichier requis")

# Lotos custom déjà en cache (hors les 13 LONATO)
custom_lotos = [l for l in list_cached_lotos() if not l.startswith("_") and l not in all_lotos]
all_lotos_display = all_lotos + custom_lotos

# ═══ UPLOAD DES FICHIERS (optionnel si cache existe) ═══
uploaded_data = {}
cached = list_cached_lotos()
nb_cached = len([l for l in cached if not l.startswith("_")])
if nb_cached:
    st.sidebar.success(f"💾 {nb_cached} loto(s) en cache — pas besoin de re-uploader !")

with st.sidebar.expander("📤 Uploader / Mettre à jour les fichiers", expanded=(nb_cached == 0)):
    for loto in all_lotos_display:
        file = st.file_uploader(f"{loto}", type=["xlsx", "xls"], key=f"up_{loto}")
        if file:
            uploaded_data[loto] = file

def parse_excel(file, loto_name):
    """Parser universel v20.9 : conserve N° tirage, date, numéros, machine, total."""
    def fmt_date(val):
        """Formate une date en jj/mm/aaaa."""
        if pd.isna(val):
            return ""
        try:
            if isinstance(val, str):
                s = val.strip()
                # déjà au format jj/mm/... → garder
                if "/" in s:
                    return s[:10]
                # format ISO aaaa-mm-jj → convertir
                return pd.Timestamp(s).strftime("%d/%m/%Y")
            return pd.Timestamp(val).strftime("%d/%m/%Y")
        except:
            return str(val)[:10]

    try:
        xls = pd.ExcelFile(file)

        # ═══ Format 1 : Tirage simple (colonnes 'tirage' + 'date' opt.) ═══
        try:
            df = pd.read_excel(file, sheet_name=0, header=0)
            df.columns = df.columns.str.strip().str.lower()

            if 'tirage' in df.columns:
                has_date = 'date' in df.columns
                num_col = next((c for c in ['n°', 'no', 'num', 'numero', 'numéro'] if c in df.columns), None)
                tirages = []
                for idx, row in df.iterrows():
                    tirage_val = row['tirage']
                    if pd.notna(tirage_val) and str(tirage_val).strip() != '':
                        nums = [int(x.strip()) for x in str(tirage_val).split() if x.strip().lstrip('-').isdigit()]
                        if len(nums) >= 5:
                            principaux = nums[:5]
                            machine = nums[5:] if len(nums) > 5 else []
                            if machine and machine[0] > 90:
                                machine = machine[1:]
                            tirages.append({
                                'num': int(row[num_col]) if (num_col and pd.notna(row.get(num_col))) else idx + 1,
                                'date': fmt_date(row['date']) if has_date else "",
                                'p': principaux,
                                'm': machine,
                                'tot': sum(principaux)
                            })
                if tirages:
                    # fichier en ordre chronologique (ancien→récent) : inverser pour récent en premier
                    tirages.reverse()
                    return tirages, len(tirages)
        except:
            pass

        # ═══ Format 2 : MATINAL / NATIONAL WEEK (header ligne 2, 1 ou 0 ; N°/Tirage/Date/N1-N5/M1-M5 ou N6-N10) ═══
        all_tirages = []
        for sheet_name in xls.sheet_names:
            df = None
            num_cols = []
            for header_row in [2, 1, 0]:
                try:
                    df_try = pd.read_excel(file, sheet_name=sheet_name, header=header_row)
                    df_try.columns = [str(c).strip().lower() for c in df_try.columns]
                    cols_try = sorted([c for c in df_try.columns if c in ['n1', 'n2', 'n3', 'n4', 'n5']])
                    if len(cols_try) >= 5:
                        df = df_try
                        num_cols = cols_try
                        break
                except:
                    pass
            if df is None:
                continue
            try:
                has_date = 'date' in df.columns
                num_col = next((c for c in ['n°', 'no', 'num', 'tirage'] if c in df.columns), None)
                sheet_tirages = []
                for idx, row in df.iterrows():
                    try:
                        nums = []
                        for col in num_cols[:5]:
                            val = row[col]
                            if pd.notna(val):
                                try:
                                    nums.append(int(float(val)))
                                except:
                                    pass
                        if len(nums) >= 5:
                            machine_cols = [col for col in df.columns if col in ['m1', 'm2', 'm3', 'm4', 'm5', 'n6', 'n7', 'n8', 'n9', 'n10']]
                            machine = []
                            for col in machine_cols:
                                val = row[col]
                                if pd.notna(val):
                                    try:
                                        v = int(float(val))
                                        if v != 0:
                                            machine.append(v)
                                    except:
                                        pass
                            sheet_tirages.append({
                                'num': int(float(row[num_col])) if (num_col and pd.notna(row.get(num_col))) else 0,
                                'date': fmt_date(row['date']) if has_date else "",
                                'p': nums[:5],
                                'm': machine,
                                'tot': sum(nums[:5])
                            })
                    except:
                        pass
                # inverser cette feuille : récent en premier
                sheet_tirages.reverse()
                all_tirages.extend(sheet_tirages)
            except:
                pass
        if all_tirages:
            # renuméroter si nums manquants
            if all(t['num'] == 0 for t in all_tirages):
                n = len(all_tirages)
                for i, t in enumerate(all_tirages):
                    t['num'] = n - i
            return all_tirages, len(all_tirages)

        return None, "Format non reconnu"
    except Exception as e:
        return None, str(e)

def nums_of(tirage):
    """Retourne les 5 numéros principaux d'un tirage (compat listes ou dicts)."""
    if isinstance(tirage, dict):
        return tirage['p']
    return tirage

def total_of(tirage):
    if isinstance(tirage, dict):
        return tirage['tot']
    return sum(tirage)

def num_of(tirage):
    """N° du tirage (0 si absent)."""
    if isinstance(tirage, dict):
        return tirage.get('num', 0)
    return 0

def date_of(tirage):
    """Date du tirage ('' si absente)."""
    if isinstance(tirage, dict):
        return tirage.get('date', '')
    return ''

W_LH_NUM, W_LH_DATE, W_LH_N, W_LH_TOT = 48, 52, 42, 58
W_LH_GAP = 3

def ligne_html(tirage, autre_set=None, manual=None, transfo_color=None, show_machine=False,
                manual_cells=None, cell_key_prefix=""):
    """Rendu unifié ALIGNÉ : N° | DATE | N1 N2 N3 N4 N5 | TOTAL collé.
    - Largeurs FIXES pour alignement vertical parfait
    - TOTAL collé aux 5 numéros (gap réduit + bordure visuelle)
    """
    if tirage is None:
        return f"<div style='color:#64748b;font-size:11px;min-width:320px;'>—</div>"
    nums = nums_of(tirage)
    # garantir 5 numéros pour l'alignement
    nums = (nums + [0]*5)[:5]
    tot = total_of(tirage)
    n = num_of(tirage)
    d = date_of(tirage)
    manual = manual or {}
    manual_cells = manual_cells or {}
    autre_set = autre_set or set()

    n_machine = len(tirage['m']) if (show_machine and isinstance(tirage, dict) and tirage.get('m')) else 0
    # Grille FIXE : N° DATE N1 N2 N3 N4 N5 TOTAL [M...]
    cols_tpl = f"{W_LH_NUM}px {W_LH_DATE}px " + " ".join([f"{W_LH_N}px"]*5) + f" {W_LH_TOT}px"
    if n_machine:
        cols_tpl += " " + " ".join([f"{W_LH_N}px"]*n_machine)

    out = f"<div style='display:grid;grid-template-columns:{cols_tpl};gap:{W_LH_GAP}px;align-items:center;justify-items:stretch;min-width:max-content;'>"
    # N° tirage - aligné à droite
    out += f"<div style='color:#0ea5e9;font-size:11px;font-weight:bold;text-align:right;padding-right:4px;overflow:hidden;'>{n if n else ''}</div>"
    # date
    out += f"<div style='color:#94a3b8;font-size:10px;text-align:center;overflow:hidden;'>{d[:5] if d else ''}</div>"
    for i, x in enumerate(nums):
        if x == 0:
            out += f"<div style='background:transparent;'></div>"
            continue
        cell_key = f"{cell_key_prefix}_{n}_{i}"
        if cell_key in manual_cells:
            bg, fg = manual_cells[cell_key], "white"
        elif x in manual:
            bg, fg = manual[x], "white"
        elif x in autre_set:
            bg, fg = "#facc15", "black"
        else:
            tc = transfo_color(x, autre_set) if transfo_color else None
            if tc:
                bg, fg = tc, "white"
            else:
                bg, fg = "#1e293b", "#e2e8f0"
        out += (f"<div style='background:{bg};color:{fg};padding:3px 0px;text-align:center;"
                f"border-radius:4px;font-size:12px;font-weight:bold;min-width:{W_LH_N}px;height:22px;display:flex;align-items:center;justify-content:center;'>{x}</div>")
    # total — COLLÉ aux résultats : couleur selon seuil, bord gauche pour marquer qu'il est collé
    if tot < 150: tc_bg = "#16a34a"
    elif tot < 250: tc_bg = "#ca8a04"
    elif tot < 300: tc_bg = "#ea580c"
    else: tc_bg = "#dc2626"
    out += (f"<div style='background:{tc_bg};color:white;padding:3px 0px;text-align:center;"
            f"border-radius:4px;font-size:11px;font-weight:900;margin-left:4px;"
            f"border-left:2px solid #0f172a;min-width:{W_LH_TOT}px;height:22px;display:flex;align-items:center;justify-content:center;'>{tot}</div>")
    # machine
    if n_machine:
        for x in tirage['m']:
            out += (f"<div style='background:#334155;color:#94a3b8;padding:2px 0px;text-align:center;"
                    f"border-radius:4px;font-size:10px;height:22px;display:flex;align-items:center;justify-content:center;'>{x}</div>")
    out += "</div>"
    return out

# ─────────────────────────────────────────────
# COLORIAGE PAR LOT + ANNULER (state via st.session_state)
# ─────────────────────────────────────────────
CC_PALETTE = ["#EF4444", "#3B82F6", "#EAB308", "#8B5CF6", "#22C55E",
              "#EC4899", "#14B8A6", "#F97316", "#6366F1", "#F59E0B"]

def push_color_undo():
    st.session_state.setdefault("color_undo_stack", [])
    snap = {
        "manual_colors": dict(st.session_state.get("manual_colors", {})),
        "manual_cells": dict(st.session_state.get("manual_cells", {})),
        "color_idx": st.session_state.get("color_idx", 0),
    }
    st.session_state.color_undo_stack.append(snap)
    if len(st.session_state.color_undo_stack) > 20:
        st.session_state.color_undo_stack.pop(0)

def undo_color():
    stack = st.session_state.get("color_undo_stack", [])
    if not stack:
        st.warning("Rien à annuler.")
        return
    snap = stack.pop()
    st.session_state.manual_colors = snap["manual_colors"]
    st.session_state.manual_cells = snap["manual_cells"]
    st.session_state.color_idx = snap["color_idx"]

def clear_all_colors():
    push_color_undo()
    st.session_state.manual_colors = {}
    st.session_state.manual_cells = {}
    st.session_state.color_idx = 0

def next_palette_color():
    idx = st.session_state.get("color_idx", 0)
    color = CC_PALETTE[idx % len(CC_PALETTE)]
    st.session_state.color_idx = idx + 1
    return color

def get_batch_color():
    """Couleur fixe choisie par l'utilisateur si activée, sinon palette qui tourne automatiquement."""
    fixed = st.session_state.get("batch_color_fixed", "")
    return fixed if fixed else next_palette_color()

def apply_batch_color(tirages_list, loto_name, mode, pos, scope):
    """Colorie plusieurs tirages d'un coup : derniers tirages / tirage N° / intervalle,
    en position "Partout" (valeur peu importe la position) ou "Position identique uniquement"."""
    if not tirages_list:
        st.warning("Aucun tirage disponible pour ce loto.")
        return
    if mode == "Derniers tirages":
        n = max(1, int(st.session_state.get("batch_n", 3)))
        rows = tirages_list[:min(n, len(tirages_list))]
    elif mode == "Tirage N°":
        tn = int(st.session_state.get("batch_tirage_no", 1))
        found = [t for t in tirages_list if num_of(t) == tn]
        if not found:
            st.error("N° de tirage introuvable pour ce loto.")
            return
        rows = found[:1]
    else:  # Intervalle
        step = max(1, int(st.session_state.get("batch_step", 2)))
        rng = max(step, int(st.session_state.get("batch_range", 20)))
        window = tirages_list[:min(rng, len(tirages_list))]
        rows = [t for i, t in enumerate(window) if i % step == 0]
    if not rows:
        st.warning("Aucun tirage trouvé pour ces réglages.")
        return

    push_color_undo()
    st.session_state.setdefault("manual_colors", {})
    st.session_state.setdefault("manual_cells", {})
    pos_indices = list(range(5)) if pos == "Tous" else [int(pos[1:]) - 1]

    if scope == "Position identique uniquement":
        for src in rows:
            color = get_batch_color()
            src_nums = nums_of(src)
            for idx in pos_indices:
                if idx >= len(src_nums):
                    continue
                val = src_nums[idx]
                for t in tirages_list:
                    tnums = nums_of(t)
                    if idx < len(tnums) and tnums[idx] == val:
                        key = f"{loto_name}_{num_of(t)}_{idx}"
                        st.session_state.manual_cells[key] = color
    else:
        for row in rows:
            color = get_batch_color()
            row_nums = nums_of(row)
            vals = row_nums if pos == "Tous" else [row_nums[idx] for idx in pos_indices if idx < len(row_nums)]
            for v in vals:
                st.session_state.manual_colors[v] = color

    st.success(f"{len(rows)} tirage(s) colorié(s) pour {loto_name}.")

# ─────────────────────────────────────────────
# GRILLE 1-90 CLIQUABLE AVEC CLASSIFICATIONS
# ─────────────────────────────────────────────
def render_grille_classifications():
    st.subheader("🎨 Grille 1-90 — Classifications")
    st.caption("Choisis un numéro pour voir ses classifications (Counter, Bonanza, Malta, etc.)")

    # Sélecteur du numéro
    num = st.number_input("Numéro à analyser", min_value=1, max_value=90, value=1, step=1)

    classifs = get_classifications(int(num))

    # Les valeurs dérivées de ce numéro (pour surligner dans la grille)
    derived = {}  # {numero_derive: (label, couleur)}
    for key, val in classifs.items():
        label, couleur = LABELS[key]
        if 1 <= val <= 90:
            derived[val] = (label, couleur)

    # Récap "popup" : toutes les transformations d'un coup (comme l'app HTML)
    from core.classification import TRANSFOS
    recap = " · ".join(f"{TRANSFOS[k]['label']}:{classifs[k]}" for k in TRANSFOS)
    st.markdown(
        f"<div style='background:#1e293b;color:#e2e8f0;padding:10px;border-radius:8px;"
        f"font-family:monospace;font-size:14px;'>🔢 <b>{int(num)}</b> → {recap}</div>",
        unsafe_allow_html=True
    )
    st.markdown("")
    # Afficher les classifications du numéro choisi
    st.markdown(f"### Classifications du **{int(num)}**")
    cols = st.columns(3)
    for i, (key, val) in enumerate(classifs.items()):
        label, couleur = LABELS[key]
        with cols[i % 3]:
            st.markdown(
                f"<div style='background:{couleur};color:white;padding:8px;border-radius:8px;"
                f"text-align:center;margin:3px;font-weight:bold;'>{label}<br><span style='font-size:22px;'>{val}</span></div>",
                unsafe_allow_html=True
            )

    st.markdown("---")
    st.markdown("### Grille 1-90")
    st.caption(f"Le numéro choisi (**{int(num)}**) est en blanc bordé. Ses dérivés sont colorés.")

    # Construire la grille HTML 10 colonnes
    html = "<div style='display:grid;grid-template-columns:repeat(10,1fr);gap:4px;'>"
    for n in range(1, 91):
        if n == int(num):
            # numéro sélectionné
            style = "background:white;color:black;border:3px solid #000;font-weight:bold;"
        elif n in derived:
            label, couleur = derived[n]
            style = f"background:{couleur};color:white;font-weight:bold;"
        else:
            style = "background:#1e293b;color:#94a3b8;"
        html += f"<div style='{style}padding:10px 0;text-align:center;border-radius:6px;font-size:16px;'>{n}</div>"
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

    # Légende
    st.markdown("---")
    st.markdown("**Légende des couleurs :**")
    leg = "<div style='display:flex;flex-wrap:wrap;gap:8px;'>"
    for key, (label, couleur) in LABELS.items():
        leg += f"<span style='background:{couleur};color:white;padding:4px 10px;border-radius:6px;font-size:13px;'>{label}</span>"
    leg += "</div>"
    st.markdown(leg, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# ALIGNEMENT + COLORIAGE (style "Comparer 2 Plages" complet)
# Jaune = identique | chaque transformation = sa couleur | coloriage manuel
# ─────────────────────────────────────────────
def render_selecteur_classif(key_prefix=""):
    """Sélecteur rapide : choisis un numéro → affiche ses 9 dérivés en ligne."""
    from core.classification import CORRESPONDANCE, TRANSFOS
    with st.expander("🔍 Classifications rapides d'un numéro"):
        num = st.number_input("Numéro (1-90)", min_value=1, max_value=90, value=25, key=f"{key_prefix}_classif_num")
        tr = CORRESPONDANCE.get(int(num), {})
        if tr:
            html = "<div style='display:flex;flex-wrap:wrap;gap:4px;font-family:monospace;font-size:13px;'>"
            html += (f"<span style='background:#0ea5e9;color:white;padding:3px 10px;"
                     f"border-radius:5px;font-weight:bold;'>N° {int(num)}</span>")
            for key, val in tr.items():
                color = TRANSFOS.get(key, {}).get('color', '#334155')
                html += (f"<span style='background:{color};color:white;padding:3px 8px;"
                         f"border-radius:5px;'>{key}: <b>{val}</b></span>")
            html += "</div>"
            st.markdown(html, unsafe_allow_html=True)


def render_alignement(data_parsed):
    from core.classification import CORRESPONDANCE, TRANSFOS

    st.subheader("🔀 Comparer 2 plages de tirages")
    st.caption("Jaune = identique. Coche les transformations à colorier. Tu peux aussi colorier un numéro à la main.")
    render_selecteur_classif("al")

    lotos = list(data_parsed.keys())

    st.markdown("#### 1️⃣ Choisis les 2 lotos et leur tirage de départ")

    # ── LIGNE 1 (loto gauche = RÉFÉRENCE FIXE) ──
    cA, cB = st.columns([2, 1])
    with cA:
        loto1 = st.selectbox("🎰 Loto 1 (gauche = référence fixe)", lotos, key="al_l1")
    t1 = data_parsed[loto1]
    max1 = max((num_of(t) for t in t1), default=1)
    with cB:
        ref1 = st.number_input(
            "N° tirage réf.", min_value=1, max_value=max1, value=max1, key="al_ref1",
            help="Par défaut : le dernier tirage"
        )

    # ── LIGNE 2 (loto droite) ──
    cC, cD = st.columns([2, 1])
    with cC:
        idx2 = 1 if len(lotos) > 1 else 0
        loto2 = st.selectbox("🎰 Loto 2 (droite)", lotos, index=idx2, key="al_l2")
    t2 = data_parsed[loto2]
    max2 = max((num_of(t) for t in t2), default=1)
    with cD:
        ref2 = st.number_input(
            "N° tirage réf.", min_value=1, max_value=max2, value=max2, key="al_ref2"
        )

    # ── Nombre de lignes ──
    nb_lignes = st.number_input(
        "📏 Nombre de lignes à afficher", min_value=5, max_value=200, value=40, key="al_nb"
    )

    st.markdown("#### 2️⃣ Options de couleur")

    # ── Choix des transformations à colorier (cases à cocher) ──
    with st.expander("🎨 Transformations à colorier"):
        cols = st.columns(3)
        actives = {}
        for i, (key, info) in enumerate(TRANSFOS.items()):
            with cols[i % 3]:
                actives[key] = st.checkbox(
                    f"{info['label']}", value=(key == "Turning"), key=f"al_tr_{key}"
                )

    # ── Coloriage manuel ──
    with st.expander("🖌️ Coloriage manuel d'un numéro"):
        cc1, cc2, cc3 = st.columns([1,1,1])
        with cc1:
            man_num = st.number_input("Numéro", min_value=1, max_value=90, value=1, key="al_man_num")
        with cc2:
            man_col = st.color_picker("Couleur", value="#e11d48", key="al_man_col")
        with cc3:
            st.write("")
            st.write("")
            if st.button("➕ Colorier", key="al_man_add", use_container_width=True):
                push_color_undo()
                if "manual_colors" not in st.session_state:
                    st.session_state.manual_colors = {}
                st.session_state.manual_colors[int(man_num)] = man_col
        if st.session_state.get("manual_colors"):
            st.caption("Coloriés à la main : " + ", ".join(
                f"{n}" for n in sorted(st.session_state.manual_colors)))

    # ── Coloriage par lot : derniers tirages / tirage N° / intervalle, avec position et choix de couleur ──
    with st.expander("🎨🔢 Coloriage par lot"):
        st.caption(f"S'applique aux tirages de **{loto1}** (le loto de référence, à gauche).")
        mode = st.radio("Mode", ["Derniers tirages", "Tirage N°", "Intervalle"], key="batch_mode", horizontal=True)
        if mode == "Derniers tirages":
            st.number_input("Nombre de derniers tirages", min_value=1, max_value=max(1, len(t1)), value=3, key="batch_n")
        elif mode == "Tirage N°":
            st.number_input("N° de tirage", min_value=1, value=1, key="batch_tirage_no")
        else:
            bc1, bc2 = st.columns(2)
            with bc1:
                st.number_input("1 tirage sur", min_value=1, value=2, key="batch_step")
            with bc2:
                st.number_input("Parmi les X derniers", min_value=1, value=20, key="batch_range")
        pos = st.selectbox("Numéro à colorier", ["Tous", "N1", "N2", "N3", "N4", "N5"], key="batch_pos")
        scope = st.radio(
            "Où chercher cette valeur", ["Partout", "Position identique uniquement"], key="batch_scope",
            horizontal=True,
            help="Partout = colore la valeur peu importe sa position. Position identique = colore "
                 "uniquement quand la même position (ex: N1) a exactement la même valeur, dans les autres tirages."
        )
        uf1, uf2 = st.columns([1, 2])
        with uf1:
            use_fixed = st.checkbox(
                "Couleur fixe", value=bool(st.session_state.get("batch_color_fixed")), key="batch_use_fixed",
                help="Décoché = chaque tirage/lot reçoit une couleur différente (palette automatique)."
            )
        with uf2:
            fixed_color = st.color_picker(
                "Couleur", value=st.session_state.get("batch_color_fixed") or "#a5501a", key="batch_fixed_color_picker"
            )
        st.session_state.batch_color_fixed = fixed_color if use_fixed else ""
        if st.button("🎨 Colorier", key="batch_apply_btn", use_container_width=True):
            apply_batch_color(t1, loto1, mode, pos, scope)

    # ── Annuler / tout effacer (couvre coloriage manuel ET coloriage par lot) ──
    uc1, uc2 = st.columns(2)
    with uc1:
        undo_n = len(st.session_state.get("color_undo_stack", []))
        if st.button(f"↩️ Annuler{f' ({undo_n})' if undo_n else ''}", key="btn_undo_color",
                     use_container_width=True, disabled=not undo_n):
            undo_color()
    with uc2:
        if st.button("🧹 Tout effacer les couleurs", key="btn_clear_all_colors", use_container_width=True):
            clear_all_colors()

    manual = st.session_state.get("manual_colors", {})
    manual_cells = st.session_state.get("manual_cells", {})

    # ── Décalage du LOTO DE DROITE uniquement (le gauche reste fixe) ──
    st.markdown(f"#### 3️⃣ Ajuster le Loto de droite ({loto2}) — le gauche reste fixe")
    if "al_offset" not in st.session_state:
        st.session_state.al_offset = 0
    b1, b2, b3 = st.columns(3)
    with b1:
        if st.button(f"▲ Monter {loto2}", use_container_width=True, key="al_up"):
            st.session_state.al_offset -= 1
    with b2:
        if st.button(f"▼ Descendre {loto2}", use_container_width=True, key="al_down"):
            st.session_state.al_offset += 1
    with b3:
        if st.button("↺ Reset", use_container_width=True, key="al_reset"):
            st.session_state.al_offset = 0
    offset = st.session_state.al_offset
    st.info(f"Décalage {loto2} (droite) : **{offset:+d}** ligne(s) • {loto1} (gauche) = fixe")

    # Convertir les N° de tirage en index (index 0 = le plus récent)
    def index_of_num(tirages, n):
        for i, t in enumerate(tirages):
            if num_of(t) == n:
                return i
        return 0

    start1 = index_of_num(t1, int(ref1))
    start2 = index_of_num(t2, int(ref2)) + offset

    def transfo_color(n, autre_nums):
        """Retourne la couleur si n est une transformation active d'un num de autre_nums."""
        for src in autre_nums:
            tr = CORRESPONDANCE.get(src, {})
            for key, active in actives.items():
                if active and tr.get(key) == n:
                    return TRANSFOS[key]['color']
        return None

    html = "<div style='font-family:monospace;font-size:12px;'>"
    html += ("<div style='display:grid;grid-template-columns:1fr 1fr;gap:0px;"
             "font-weight:bold;padding:2px;border-bottom:2px solid #475569;'>"
             f"<div style='padding:0 2px;'>{loto1}</div><div style='padding:0 2px;'>{loto2}</div></div>")

    # ── Ligne vide "tirage à venir" (au-dessus de la référence gauche) ──
    prochain1 = num_of(t1[start1]) + 1 if start1 < len(t1) else 1
    vide = ("<span style='color:#64748b;font-size:10px;'>" + str(prochain1) + "</span> "
            + "".join("<span style='border:1px dashed #475569;color:transparent;padding:0px 3px;"
                      "border-radius:2px;display:inline-block;font-size:11px;margin:0 1px;'>00</span>" for _ in range(5)))
    html += (f"<div style='display:grid;grid-template-columns:1fr 1fr;gap:0px;"
             f"padding:1px 0px;background:#1e293b;align-items:center;'>"
             f"<div style='padding:0 2px;font-size:11px;'>{vide}</div>"
             f"<div style='padding:0 2px;'></div></div>")

    # Le loto de droite affiche 10 lignes de plus en bas
    for k in range(int(nb_lignes) + 10):
        i = start1 + k
        j = start2 + k
        gauche_fini = (i >= len(t1)) or (k >= int(nb_lignes))
        droite_finie = (j < 0) or (j >= len(t2))
        if gauche_fini and droite_finie:
            break
        tir1_obj = t1[i] if not gauche_fini else None
        tir2_obj = t2[j] if not droite_finie else None
        set1 = set(nums_of(tir1_obj)) if tir1_obj else set()
        set2 = set(nums_of(tir2_obj)) if tir2_obj else set()

        c1h = ligne_html(tir1_obj, autre_set=set2, manual=manual, transfo_color=transfo_color,
                          manual_cells=manual_cells, cell_key_prefix=loto1) if tir1_obj else ""
        c2h = ligne_html(tir2_obj, autre_set=set1, manual=manual, transfo_color=transfo_color,
                          manual_cells=manual_cells, cell_key_prefix=loto2)
        bg = "#0f172a" if k % 2 == 0 else "#020617"
        html += (f"<div style='display:grid;grid-template-columns:1fr 1fr;gap:0px;"
                 f"padding:1px 0px;background:{bg};align-items:center;'>"
                 f"<div style='padding:0 2px;font-size:11px;overflow-x:auto;'>{c1h}</div>"
                 f"<div style='padding:0 2px;font-size:11px;overflow-x:auto;'>{c2h}</div></div>")
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

    # Légende
    st.markdown("**Légende :**")
    leg = "<div style='display:flex;flex-wrap:wrap;gap:6px;'>"
    leg += "<span style='background:#facc15;color:black;padding:3px 10px;border-radius:6px;font-size:12px;font-weight:bold;'>Identique</span>"
    for key, active in actives.items():
        if active:
            info = TRANSFOS[key]
            leg += f"<span style='background:{info['color']};color:white;padding:3px 10px;border-radius:6px;font-size:12px;'>{info['label']}</span>"
    leg += "</div>"
    st.markdown(leg, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# NAVIGATION : voir un loto seul (tirages + Total coloré)
# ─────────────────────────────────────────────
def render_navigation(data_parsed):
    st.subheader("📋 Navigation — Tirages d'un loto")
    render_selecteur_classif("nav")

    lotos = list(data_parsed.keys())
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    with c1:
        loto = st.selectbox("🎰 Loto à consulter", lotos, key="nav_loto")
    with c2:
        nb = st.number_input("Nb tirages affichés", min_value=5, max_value=500, value=30, key="nav_nb")
    with c3:
        nb_recents = st.number_input("🔦 Colorier N derniers", min_value=0, max_value=20, value=3, key="nav_recents",
                                     help="Met en surbrillance les N tirages les plus récents")
    with c4:
        style = st.selectbox("🎨 Style", ["Compact", "Normal", "Large"], index=1, key="nav_style")

    # ═══ POT DE PEINTURE ═══
    with st.expander("🎨 Pot de peinture — colorier des lignes spécifiques"):
        c1, c2 = st.columns([2, 1])
        with c1:
            indices_txt = st.text_input(
                "Numéros de lignes à colorier (séparés par virgule)",
                value="",
                placeholder="Ex: 1, 3, 5, 12",
                key="nav_pot_idx"
            )
        with c2:
            couleur_pot = st.color_picker("Couleur", value="#3b82f6", key="nav_pot_c")
        # Parse indices
        indices_pot = set()
        for x in indices_txt.replace(";", ",").split(","):
            x = x.strip()
            if x.isdigit():
                indices_pot.add(int(x))

    tirages = data_parsed[loto]
    st.caption(f"**{loto}** — {len(tirages)} tirages au total. Affichage du plus récent au plus ancien.")

    # Couleur du total selon seuils
    def couleur_total(t):
        if t < 150:  return "#22c55e"
        if t < 250:  return "#eab308"
        if t < 300:  return "#f97316"
        return "#ef4444"

    # Paramètres selon style
    if style == "Compact":
        font_size, pad_row, pad_num, num_pad_x = "12px", "3px", "2px 6px", "6px"
        gap = "3px"
    elif style == "Large":
        font_size, pad_row, pad_num, num_pad_x = "17px", "10px", "6px 12px", "12px"
        gap = "6px"
    else:  # Normal
        font_size, pad_row, pad_num, num_pad_x = "15px", "6px", "4px 9px", "9px"
        gap = "4px"

    # ═══ Rendu ALIGNÉ + TOTAUX COLLÉS ═══
    # Grille unique : N° | Date | N1 N2 N3 N4 N5 | TOTAL collé
    # Largeurs fixes pour alignement parfait
    if style == "Compact":
        W_N, W_D, W_B, W_T = 50, 55, 40, 54
        fsz = "13px"
    elif style == "Large":
        W_N, W_D, W_B, W_T = 60, 65, 52, 68
        fsz = "17px"
    else:
        W_N, W_D, W_B, W_T = 55, 60, 46, 60
        fsz = "15px"

    html = f"<div style='font-family:monospace;font-size:{fsz};overflow-x:auto;'>"
    # Header aligné
    html += (f"<div style='display:grid;grid-template-columns:{W_N}px {W_D}px repeat(5,{W_B}px) {W_T}px;"
             f"gap:4px;padding:6px 4px;font-weight:bold;border-bottom:2px solid #475569;background:#0f172a;position:sticky;top:0;z-index:10;'>"
             f"<div style='text-align:right;color:#94a3b8;'>N°</div>"
             f"<div style='text-align:center;color:#94a3b8;'>Date</div>"
             f"<div style='text-align:center;'>N1</div><div style='text-align:center;'>N2</div><div style='text-align:center;'>N3</div><div style='text-align:center;'>N4</div><div style='text-align:center;'>N5</div>"
             f"<div style='text-align:center;color:#fbbf24;margin-left:6px;border-left:2px solid #334155;padding-left:6px;'>Total</div>"
             f"</div>")

    for i in range(min(int(nb), len(tirages))):
        ligne = tirages[i]
        nums = nums_of(ligne)[:5]
        total = sum(nums)
        num_t = num_of(ligne)
        date_t = date_of(ligne)
        is_recent = i < int(nb_recents)
        is_pot = (i+1) in indices_pot

        if is_recent:
            bg = "#422006"
            border = "border-left:4px solid #fbbf24;"
        elif is_pot:
            bg = "#1e3a8a"
            border = f"border-left:4px solid {couleur_pot};"
        else:
            bg = "#0f172a" if i % 2 == 0 else "#020617"
            border = ""

        # cellules numéros
        cells_html = ""
        for n in nums:
            if is_recent:
                st_bg = "#fbbf24"; fg="#0f172a"
            elif is_pot:
                st_bg = couleur_pot; fg="white"
            else:
                st_bg = "#1e293b"; fg="#e2e8f0"
            cells_html += (f"<div style='background:{st_bg};color:{fg};border-radius:6px;font-weight:bold;"
                           f"height:26px;display:flex;align-items:center;justify-content:center;'>{n}</div>")

        ct = couleur_total(total)
        tot_html = (f"<div style='background:{ct};color:white;border-radius:6px;font-weight:900;"
                    f"height:26px;display:flex;align-items:center;justify-content:center;margin-left:6px;border-left:2px solid #0f172a;'>{total}</div>")

        html += (f"<div style='display:grid;grid-template-columns:{W_N}px {W_D}px repeat(5,{W_B}px) {W_T}px;"
                 f"gap:4px;padding:4px;background:{bg};{border}align-items:center;'>"
                 f"<div style='color:#0ea5e9;font-weight:bold;text-align:right;padding-right:6px;'>{num_t if num_t else i+1}</div>"
                 f"<div style='color:#94a3b8;font-size:0.9em;text-align:center;'>{date_t[:5] if date_t else ''}</div>"
                 f"{cells_html}"
                 f"{tot_html}"
                 f"</div>")

    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)
    st.markdown("<div style='color:#22c55e;font-size:11px;margin-top:4px;'>✅ Résultats alignés • Totaux collés directement aux 5 boules</div>", unsafe_allow_html=True)

    # Légende des totaux
    st.markdown("**Légende Total :** "
        "<span style='background:#22c55e;color:white;padding:2px 8px;border-radius:5px;'>&lt;150</span> "
        "<span style='background:#eab308;color:white;padding:2px 8px;border-radius:5px;'>150-249</span> "
        "<span style='background:#f97316;color:white;padding:2px 8px;border-radius:5px;'>250-299</span> "
        "<span style='background:#ef4444;color:white;padding:2px 8px;border-radius:5px;'>≥300</span>",
        unsafe_allow_html=True)


# ─────────────────────────────────────────────
# COMPARER 3 PLAGES (3 lotos côte à côte)
# ─────────────────────────────────────────────
def render_3plages(data_parsed):
    from core.classification import CORRESPONDANCE, TRANSFOS

    st.subheader("🔀 Comparer 3 plages de tirages")
    st.caption("3 lotos côte à côte. Gauche = fixe. Milieu et droite ajustables. Jaune = identique, couleurs = transformations.")
    render_selecteur_classif("p3")

    lotos = list(data_parsed.keys())

    st.markdown("#### 1️⃣ Choisis les 3 lotos et leurs lignes de départ")
    rows_cfg = []
    for idx, lab in enumerate(["Loto 1 (gauche, fixe)", "Loto 2 (milieu)", "Loto 3 (droite)"]):
        cA, cB = st.columns([2,1])
        with cA:
            default = min(idx, len(lotos)-1)
            lo = st.selectbox(f"🎰 {lab}", lotos, index=default, key=f"p3_lo_{idx}")
        with cB:
            dep = st.number_input(f"🔢 Ligne {idx+1}", min_value=1,
                                  max_value=len(data_parsed[lo]), value=1, key=f"p3_dep_{idx}")
        rows_cfg.append((lo, dep))

    nb_lignes = st.number_input("📏 Nombre de lignes", min_value=5, max_value=100, value=30, key="p3_nb")

    st.markdown("#### 2️⃣ Transformations à colorier")
    with st.expander("🎨 Choisir"):
        cols = st.columns(3)
        actives = {}
        for i,(key,info) in enumerate(TRANSFOS.items()):
            with cols[i%3]:
                actives[key] = st.checkbox(info['label'], value=(key=="Turning"), key=f"p3_tr_{key}")

    # Décalages pour loto 2 et 3
    st.markdown("#### 3️⃣ Ajuster milieu et droite (gauche = fixe)")
    for slot in [1,2]:
        key_off = f"p3_off_{slot}"
        if key_off not in st.session_state:
            st.session_state[key_off] = 0
        lo = rows_cfg[slot][0]
        b1,b2,b3 = st.columns(3)
        with b1:
            if st.button(f"▲ {lo}", use_container_width=True, key=f"p3_up_{slot}"):
                st.session_state[key_off] -= 1
        with b2:
            if st.button(f"▼ {lo}", use_container_width=True, key=f"p3_dn_{slot}"):
                st.session_state[key_off] += 1
        with b3:
            if st.button(f"↺ {lo}", use_container_width=True, key=f"p3_rs_{slot}"):
                st.session_state[key_off] = 0

    offs = [0, st.session_state.get("p3_off_1",0), st.session_state.get("p3_off_2",0)]

    def transfo_color(n, autre_nums):
        for src in autre_nums:
            tr = CORRESPONDANCE.get(src, {})
            for key, active in actives.items():
                if active and tr.get(key) == n:
                    return TRANSFOS[key]['color']
        return None

    # Récupérer les données de chaque colonne
    data = []
    for slot,(lo,dep) in enumerate(rows_cfg):
        t = data_parsed[lo]
        start = dep - 1 + offs[slot]
        data.append((lo, t, start))

    # En-tête
    html = "<div style='font-family:monospace;font-size:12px;'>"
    cols_tpl = " ".join(["1fr"]*3)
    html += f"<div style='display:grid;grid-template-columns:{cols_tpl};gap:0px;font-weight:bold;padding:2px;border-bottom:2px solid #475569;'>"
    for lo,_,_ in data:
        html += f"<div style='padding:0 2px;'>{lo}</div>"
    html += "</div>"

    # Reference = loto 1 pour comparer identique/miroir
    for k in range(int(nb_lignes)):
        i0 = data[0][2] + k
        if i0 >= len(data[0][1]):
            break
        # tirages de chaque colonne
        tirs = []
        for lo,t,start in data:
            j = start + k
            tirs.append(t[j] if 0 <= j < len(t) else None)
        ref = set(nums_of(tirs[0])) if tirs[0] else set()

        bg = "#0f172a" if k%2==0 else "#020617"
        html += f"<div style='display:grid;grid-template-columns:{cols_tpl};gap:0px;padding:1px 0px;background:{bg};align-items:center;'>"
        for ci, tir in enumerate(tirs):
            if ci == 0:
                cell = ligne_html(tir)  # colonne référence neutre
            else:
                cell = ligne_html(tir, autre_set=ref, transfo_color=transfo_color)
            html += f"<div style='padding:0 2px;font-size:11px;overflow-x:auto;'>{cell}</div>"
        html += "</div>"
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)
    st.caption("Colonne 1 = référence. Milieu et droite colorés selon leur rapport au loto 1.")


# ─────────────────────────────────────────────
# COMPARAISON DES TOTAUX (2 lotos alignés)
# ─────────────────────────────────────────────
def render_totaux(data_parsed):
    st.subheader("🔢 Comparaison des Totaux")
    st.caption("Aligne 2 lotos. Total identique = jaune. Total miroir (ex: 253↔352) = vert.")

    lotos = list(data_parsed.keys())
    cA, cB = st.columns([2,1])
    with cA:
        loto1 = st.selectbox("🎰 Loto 1 (gauche)", lotos, key="tot_l1")
    t1 = data_parsed[loto1]
    with cB:
        dep1 = st.number_input("🔢 Ligne 1", min_value=1, max_value=len(t1), value=1, key="tot_d1")

    cC, cD = st.columns([2,1])
    with cC:
        idx2 = 1 if len(lotos)>1 else 0
        loto2 = st.selectbox("🎰 Loto 2 (droite)", lotos, index=idx2, key="tot_l2")
    t2 = data_parsed[loto2]
    with cD:
        dep2 = st.number_input("🔢 Ligne 2", min_value=1, max_value=len(t2), value=1, key="tot_d2")

    nb = st.number_input("📏 Nombre de lignes", min_value=5, max_value=100, value=40, key="tot_nb")

    if "tot_off" not in st.session_state:
        st.session_state.tot_off = 0
    b1,b2,b3 = st.columns(3)
    with b1:
        if st.button(f"▲ Monter {loto2}", use_container_width=True, key="tot_up"):
            st.session_state.tot_off -= 1
    with b2:
        if st.button(f"▼ Descendre {loto2}", use_container_width=True, key="tot_dn"):
            st.session_state.tot_off += 1
    with b3:
        if st.button("↺ Reset", use_container_width=True, key="tot_rs"):
            st.session_state.tot_off = 0
    offset = st.session_state.tot_off

    def miroir_total(t):
        # miroir d'un nombre = chiffres inversés (253 -> 352)
        return int(str(t)[::-1])

    start1 = dep1 - 1
    start2 = dep2 - 1 + offset

    html = "<div style='font-family:monospace;font-size:12px;'>"
    html += ("<div style='display:grid;grid-template-columns:1fr 1fr;gap:0px;"
             "font-weight:bold;padding:2px;border-bottom:2px solid #475569;'>"
             f"<div style='padding:0 2px;'>{loto1}</div><div style='padding:0 2px;'>{loto2}</div></div>")

    nb_id = 0
    nb_mir = 0
    for k in range(int(nb)):
        i = start1 + k
        j = start2 + k
        if i >= len(t1):
            break
        tir1 = t1[i]
        tir2 = t2[j] if 0 <= j < len(t2) else None
        tot1 = total_of(tir1)
        tot2 = total_of(tir2) if tir2 else None

        # marquage total identique / miroir
        if tot2 is not None and tot1 == tot2:
            nb_id += 1
            hl = "outline:2px solid #facc15;"
        elif tot2 is not None and tot1 == miroir_total(tot2):
            nb_mir += 1
            hl = "outline:2px solid #22c55e;"
        else:
            hl = ""

        c1h = ligne_html(tir1)
        c2h = ligne_html(tir2)
        bg = "#0f172a" if k%2==0 else "#020617"
        html += (f"<div style='display:grid;grid-template-columns:1fr 1fr;gap:0px;"
                 f"padding:1px 0px;background:{bg};align-items:center;{hl}'>"
                 f"<div style='padding:0 2px;font-size:11px;overflow-x:auto;'>{c1h}</div>"
                 f"<div style='padding:0 2px;font-size:11px;overflow-x:auto;'>{c2h}</div></div>")
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

    c1,c2 = st.columns(2)
    with c1:
        st.markdown(f"<div style='background:#facc15;color:black;padding:8px;border-radius:8px;text-align:center;font-weight:bold;'>🟡 Totaux identiques : {nb_id}</div>", unsafe_allow_html=True)
    with c2:
        st.markdown(f"<div style='background:#22c55e;color:white;padding:8px;border-radius:8px;text-align:center;font-weight:bold;'>🟢 Totaux miroirs : {nb_mir}</div>", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# RECHERCHE TOTAUX (total vs numéros, lignes consécutives)
# ─────────────────────────────────────────────
def render_recherche_totaux(data_parsed):
    st.subheader("🔍 Recherche sur les Totaux")
    st.caption("Détecte : total présent dans le tirage, total = numéro de la ligne d'avant, totaux consécutifs identiques.")

    lotos = list(data_parsed.keys())
    c1, c2 = st.columns([2,1])
    with c1:
        loto = st.selectbox("🎰 Loto", lotos, key="rt_loto")
    with c2:
        nb = st.number_input("Nb lignes", min_value=10, max_value=300, value=50, key="rt_nb")

    st.markdown("**Cas à détecter :**")
    d1 = st.checkbox("🟢 Total présent dans le MÊME tirage", value=True, key="rt_d1")
    d2 = st.checkbox("🔵 Total = un numéro de la ligne d'AVANT", value=True, key="rt_d2")
    d3 = st.checkbox("🟡 Total identique à la ligne consécutive", value=True, key="rt_d3")

    tirages = data_parsed[loto]

    W_NUM, W_TOT = 50, 90
    cnt1 = cnt2 = cnt3 = 0
    n_show = min(int(nb), len(tirages))
    lignes = []
    for i in range(n_show):
        ligne = nums_of(tirages[i])[:5]
        total = sum(ligne)
        # ligne d'avant (plus récente est i-1 ? non : i est plus récent, i+1 plus ancien)
        # "ligne d'avant" chronologiquement = tirage précédent = i+1 (plus ancien)
        prev = nums_of(tirages[i+1])[:5] if i+1 < len(tirages) else None
        # ligne suivante affichée (consécutive) = i+1
        total_prev = sum(prev) if prev else None

        # détections
        hit_same = d1 and (total in ligne)
        hit_prev = d2 and prev and (total in prev)
        hit_consec = d3 and total_prev is not None and (total == total_prev)

        # couleur du total selon détection prioritaire
        if hit_same:
            ct, lab = "#22c55e", "T∈tirage"; cnt1 += 1
        elif hit_consec:
            ct, lab = "#eab308", "T=T-1"; cnt3 += 1
        else:
            ct, lab = "#334155", ""

        cells = ""
        for n in ligne:
            cells += f"<span style='background:#1e293b;color:#e2e8f0;padding:3px 8px;border-radius:5px;margin:1px;display:inline-block;font-weight:bold;'>{n}</span>"

        badge_prev = ""
        if hit_prev:
            cnt2 += 1
            badge_prev = "<span style='background:#3b82f6;color:white;padding:2px 7px;border-radius:5px;margin-left:6px;font-size:12px;'>T dans ligne d'avant</span>"

        tot_html = f"<span style='background:{ct};color:white;padding:3px 10px;border-radius:5px;font-weight:bold;'>{total}</span>"
        if lab:
            tot_html += f" <span style='color:#94a3b8;font-size:11px;'>{lab}</span>"

        bg = "#0f172a" if i%2==0 else "#020617"
        lignes.append({"idx": i+1, "cells": cells, "badge_prev": badge_prev, "tot_html": tot_html, "bg": bg})

    st.markdown("<div style='color:#94a3b8;font-size:11px;margin-bottom:4px;'>📌 Colonnes « # » et « Total » figées lors du scroll horizontal</div>", unsafe_allow_html=True)

    html = "<div style='display:flex;overflow-x:auto;font-family:monospace;font-size:15px;'>"

    # Colonne figée #
    html += f"<div style='position:sticky;left:0;z-index:11;width:{W_NUM}px;flex:0 0 {W_NUM}px;'>"
    html += "<div style='font-weight:bold;padding:6px;border-bottom:2px solid #475569;background:#0f172a;'>#</div>"
    for l in lignes:
        html += f"<div style='padding:6px;background:{l['bg']};color:#64748b;'>{l['idx']}</div>"
    html += "</div>"

    # Colonne scrollable Numéros (+ badge)
    html += "<div style='flex:1 1 auto;min-width:0;overflow-x:auto;'>"
    html += "<div style='font-weight:bold;padding:6px;border-bottom:2px solid #475569;white-space:nowrap;'>Numéros</div>"
    for l in lignes:
        html += f"<div style='padding:6px;background:{l['bg']};white-space:nowrap;'>{l['cells']}{l['badge_prev']}</div>"
    html += "</div>"

    # Colonne figée Total
    html += f"<div style='position:sticky;right:0;z-index:11;width:{W_TOT}px;flex:0 0 {W_TOT}px;'>"
    html += "<div style='font-weight:bold;padding:6px;border-bottom:2px solid #475569;background:#0f172a;text-align:center;'>Total</div>"
    for l in lignes:
        html += f"<div style='padding:6px;background:{l['bg']};text-align:center;'>{l['tot_html']}</div>"
    html += "</div>"

    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

    cc1, cc2, cc3 = st.columns(3)
    with cc1:
        st.markdown(f"<div style='background:#22c55e;color:white;padding:8px;border-radius:8px;text-align:center;font-weight:bold;'>🟢 T dans tirage : {cnt1}</div>", unsafe_allow_html=True)
    with cc2:
        st.markdown(f"<div style='background:#3b82f6;color:white;padding:8px;border-radius:8px;text-align:center;font-weight:bold;'>🔵 T ligne d'avant : {cnt2}</div>", unsafe_allow_html=True)
    with cc3:
        st.markdown(f"<div style='background:#eab308;color:white;padding:8px;border-radius:8px;text-align:center;font-weight:bold;'>🟡 T consécutifs : {cnt3}</div>", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# SÉQUENCE DE NUMÉROS
# ─────────────────────────────────────────────
def render_sequence(data_parsed):
    st.subheader("🧬 Séquence de numéros")
    st.caption("Trouve les séquences : un numéro (ou groupe) apparaît, puis X lignes plus loin un autre numéro, etc.")

    lotos = list(data_parsed.keys())

    # Sélection du jeu
    c1, c2 = st.columns([2, 1])
    with c1:
        cible = st.selectbox(
            "🎰 Jeu(x) à analyser",
            ["📚 Tous les jeux"] + lotos,
            key="seq_cible"
        )
    with c2:
        nb_niveaux = st.number_input("Nb niveaux", min_value=2, max_value=6, value=3, key="seq_nb_niv")

    st.markdown("**Configuration des niveaux** (jusqu'à 5 numéros par niveau, décalage = nb lignes après le niveau précédent) :")

    # Grille de saisie des niveaux
    niveaux = []
    for k in range(int(nb_niveaux)):
        st.markdown(f"<div style='background:#1e293b;padding:8px;border-radius:6px;margin-top:6px;'><b style='color:#93c5fd;'>Niveau {k+1}</b></div>", unsafe_allow_html=True)
        cols = st.columns([1, 1, 1, 1, 1, 1])
        # Décalage (niveau 1 = pas de décalage)
        with cols[0]:
            if k == 0:
                st.caption("Décalage")
                st.markdown("<div style='padding:8px;color:#64748b;'>—</div>", unsafe_allow_html=True)
                dec = 0
            else:
                dec = st.number_input("Décalage", min_value=1, max_value=50, value=1, key=f"seq_dec_{k}")
        # 5 slots pour les numéros
        nums = []
        for j in range(5):
            with cols[j + 1]:
                v = st.number_input(f"N{j+1}", min_value=0, max_value=90, value=0, key=f"seq_n_{k}_{j}", label_visibility="visible")
                if v > 0:
                    nums.append(int(v))
        niveaux.append({'decalage': int(dec), 'nums': nums})

    # Validation
    invalides = [i+1 for i, n in enumerate(niveaux) if len(n['nums']) == 0]
    if invalides:
        st.warning(f"⚠️ Renseigne au moins 1 numéro pour les niveaux : {invalides}")
        return

    # Bouton recherche
    lancer = st.button("🔍 Rechercher la séquence", type="primary", use_container_width=True, key="seq_go")
    if not lancer:
        return

    # Jeux à parcourir
    jeux_a_chercher = lotos if cible == "📚 Tous les jeux" else [cible]

    # Recherche
    # tirages[0] = plus récent, tirages[-1] = plus ancien
    # "1 ligne après" (chronologiquement plus tard) = index PLUS PETIT
    # Mais visuellement dans la capture, on voit le tirage 62 puis 63 puis 64 = ordre chronologique croissant
    # Donc "décalage 1" = ligne SUIVANTE dans l'ordre chronologique = index +1 si on lit dans l'ordre ancien→récent
    # Comme tirages[0] = plus récent, on parcourt à l'ENVERS et un décalage = -1 dans l'index
    # Pour simplifier : on renverse la liste et on travaille chronologiquement
    trouvees = []  # liste de dicts {jeu, positions:[(idx_dans_ordre_chrono, num_trouve), ...]}

    for jeu in jeux_a_chercher:
        tirs = data_parsed[jeu]
        # Convertir en ordre chronologique (ancien → récent)
        # tirs[0] = plus récent, donc on inverse
        chrono = list(reversed(tirs))
        n = len(chrono)

        # Pour chaque tirage candidat comme point de départ (niveau 1)
        for i0 in range(n):
            nums_i0 = nums_of(chrono[i0])
            n1_trouve = next((x for x in niveaux[0]['nums'] if x in nums_i0), None)
            if n1_trouve is None:
                continue
            # Essayer de compléter la chaîne
            positions = [(i0, n1_trouve)]
            i_curr = i0
            ok = True
            for k in range(1, len(niveaux)):
                i_curr = i_curr + niveaux[k]['decalage']
                if i_curr >= n:
                    ok = False
                    break
                nums_curr = nums_of(chrono[i_curr])
                nk_trouve = next((x for x in niveaux[k]['nums'] if x in nums_curr), None)
                if nk_trouve is None:
                    ok = False
                    break
                positions.append((i_curr, nk_trouve))
            if ok:
                trouvees.append({'jeu': jeu, 'positions': positions, 'chrono': chrono})

    # Résultats
    if not trouvees:
        st.warning("Aucune séquence trouvée avec ces paramètres.")
        return

    st.success(f"✅ {len(trouvees)} séquence(s) trouvée(s)")

    # Pagination
    par_page = st.selectbox("Séquences par page", [5, 10, 20, 50], index=1, key="seq_pp")
    total_pages = (len(trouvees) + par_page - 1) // par_page
    page = st.number_input(f"Page (1 à {total_pages})", min_value=1, max_value=max(1, total_pages), value=1, key="seq_page")
    debut = (page - 1) * par_page
    fin = min(debut + par_page, len(trouvees))

    # Affichage : chaque séquence = un bloc avec les tirages concernés, numéros encadrés en violet
    for seq in trouvees[debut:fin]:
        jeu = seq['jeu']
        chrono = seq['chrono']
        positions = seq['positions']  # [(idx_chrono, num), ...]
        idx_positions = {p[0]: p[1] for p in positions}

        # Header
        html = f"<div style='background:#1e40af;color:white;padding:8px 12px;border-radius:6px 6px 0 0;font-weight:bold;'>📌 {jeu} — Séquence</div>"
        html += "<div style='background:#0f172a;padding:8px;border-radius:0 0 6px 6px;font-family:monospace;font-size:14px;'>"

        # On affiche les tirages de la séquence (avec éventuellement un contexte)
        for idx_chrono, num_trouve in positions:
            # Numéro du tirage (dans l'ordre chronologique inversé pour affichage type "index/total")
            num_tirage_original = len(chrono) - idx_chrono  # numéro d'origine dans data_parsed
            nums = nums_of(chrono[idx_chrono])
            total = sum(nums)

            cells = ""
            for n in nums:
                if n == num_trouve:
                    # Encadré violet (comme la capture)
                    cells += (f"<span style='background:transparent;color:#e879f9;padding:3px 8px;"
                              f"border:2px solid #e879f9;border-radius:5px;margin:2px;display:inline-block;"
                              f"font-weight:bold;'>{n}</span>")
                else:
                    cells += (f"<span style='background:#1e293b;color:#e2e8f0;padding:3px 8px;"
                              f"border-radius:5px;margin:2px;display:inline-block;'>{n}</span>")

            html += (f"<div style='padding:5px;display:grid;grid-template-columns:80px 1fr 70px;gap:10px;align-items:center;'>"
                     f"<div style='color:#94a3b8;'>{jeu} #{num_tirage_original}</div>"
                     f"<div>{cells}</div>"
                     f"<div style='color:#64748b;'>Tot: {total}</div></div>")

        html += "</div>"
        st.markdown(html, unsafe_allow_html=True)
        st.markdown("")


# ─────────────────────────────────────────────
# SUITES MATHÉMATIQUES CÉLÈBRES
# ─────────────────────────────────────────────
SUITES = {
    "Nombres premiers":     [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79, 83, 89],
    "Nombres pairs":        list(range(2, 91, 2)),
    "Nombres impairs":      list(range(1, 91, 2)),
    "Multiples de 3":       list(range(3, 91, 3)),
    "Multiples de 5":       list(range(5, 91, 5)),
    "Multiples de 7":       list(range(7, 91, 7)),
    "Multiples de 9":       list(range(9, 91, 9)),
    "Multiples de 11":      list(range(11, 91, 11)),
    "Nombres carrés":       [1, 4, 9, 16, 25, 36, 49, 64, 81],
    "Nombres cubes":        [1, 8, 27, 64],
    "Fibonacci":            [1, 2, 3, 5, 8, 13, 21, 34, 55, 89],
    "Nombres triangulaires":[1, 3, 6, 10, 15, 21, 28, 36, 45, 55, 66, 78],
    "Puissances de 2":      [2, 4, 8, 16, 32, 64],
    "Puissances de 3":      [3, 9, 27, 81],
    "Nombres pentagonaux":  [1, 5, 12, 22, 35, 51, 70],
    "Nombres hexagonaux":   [1, 6, 15, 28, 45, 66],
    "Nombres de Lucas":     [1, 3, 4, 7, 11, 18, 29, 47, 76],
    "Nombres palindromes":  [1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 22, 33, 44, 55, 66, 77, 88],
    "Nombres parfaits":     [6, 28],
}

def render_suites(data_parsed):
    st.subheader("🔢 Suites mathématiques")
    st.caption("Détecte les numéros appartenant à des suites mathématiques célèbres dans les derniers tirages.")

    lotos = list(data_parsed.keys())
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        loto = st.selectbox("🎰 Loto", lotos, key="suite_loto")
    with c2:
        nb = st.number_input("Nb tirages analysés", min_value=5, max_value=200, value=30, key="suite_nb")
    with c3:
        suite_nom = st.selectbox("📐 Suite", list(SUITES.keys()), key="suite_nom")

    suite = set(SUITES[suite_nom])
    tirages = data_parsed[loto][:int(nb)]

    st.markdown(f"**Suite « {suite_nom} »** ({len(suite)} numéros) : "
                + " ".join(f"<span style='background:#7c3aed;color:white;padding:2px 6px;border-radius:4px;margin:1px;display:inline-block;font-size:12px;'>{n}</span>" for n in sorted(suite)),
                unsafe_allow_html=True)

    st.markdown("")

    # Analyse tirage par tirage — # et Match figés, Numéros scrollable
    W_NUM, W_MATCH = 50, 80
    total_matches = 0
    tirages_avec_match = 0
    lignes = []
    for i, tir in enumerate(tirages):
        nums = nums_of(tir)[:5]
        matches = [n for n in nums if n in suite]
        nb_match = len(matches)
        if nb_match > 0:
            tirages_avec_match += 1
            total_matches += nb_match

        cells = ""
        for n in nums:
            if n in suite:
                cells += (f"<span style='background:#7c3aed;color:white;padding:4px 9px;"
                          f"border-radius:6px;margin:2px;display:inline-block;font-weight:bold;"
                          f"box-shadow:0 0 4px rgba(124,58,237,0.5);'>{n}</span>")
            else:
                cells += (f"<span style='background:#1e293b;color:#94a3b8;padding:4px 9px;"
                          f"border-radius:6px;margin:2px;display:inline-block;'>{n}</span>")

        badge_color = "#7c3aed" if nb_match > 0 else "#334155"
        badge = f"<span style='background:{badge_color};color:white;padding:3px 10px;border-radius:5px;font-weight:bold;'>{nb_match}/5</span>"

        bg = "#0f172a" if i % 2 == 0 else "#020617"
        lignes.append({"idx": i+1, "cells": cells, "badge": badge, "bg": bg})

    st.markdown("<div style='color:#94a3b8;font-size:11px;margin-bottom:4px;'>📌 Colonnes « # » et « Match » figées lors du scroll horizontal</div>", unsafe_allow_html=True)

    html = "<div style='display:flex;overflow-x:auto;font-family:monospace;font-size:14px;'>"

    # Colonne figée #
    html += f"<div style='position:sticky;left:0;z-index:11;width:{W_NUM}px;flex:0 0 {W_NUM}px;'>"
    html += "<div style='font-weight:bold;padding:6px;border-bottom:2px solid #475569;background:#0f172a;'>#</div>"
    for l in lignes:
        html += f"<div style='padding:6px;background:{l['bg']};color:#64748b;'>{l['idx']}</div>"
    html += "</div>"

    # Colonne scrollable Numéros
    html += "<div style='flex:1 1 auto;min-width:0;overflow-x:auto;'>"
    html += "<div style='font-weight:bold;padding:6px;border-bottom:2px solid #475569;white-space:nowrap;'>Numéros</div>"
    for l in lignes:
        html += f"<div style='padding:6px;background:{l['bg']};white-space:nowrap;'>{l['cells']}</div>"
    html += "</div>"

    # Colonne figée Match
    html += f"<div style='position:sticky;right:0;z-index:11;width:{W_MATCH}px;flex:0 0 {W_MATCH}px;'>"
    html += "<div style='font-weight:bold;padding:6px;border-bottom:2px solid #475569;background:#0f172a;text-align:center;'>Match</div>"
    for l in lignes:
        html += f"<div style='padding:6px;background:{l['bg']};text-align:center;'>{l['badge']}</div>"
    html += "</div>"

    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

    # Stats
    st.markdown("")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Tirages avec match", f"{tirages_avec_match}/{len(tirages)}")
    with c2:
        st.metric("Total numéros trouvés", total_matches)
    with c3:
        moy = total_matches / len(tirages) if tirages else 0
        st.metric("Moyenne/tirage", f"{moy:.2f}")


# ─────────────────────────────────────────────
# RETARDS
# ─────────────────────────────────────────────
def render_retards(data_parsed):
    st.subheader("⏱️ Retards — Numéros absents")
    st.caption("Depuis combien de tirages chaque numéro n'est-il pas sorti ?")

    lotos = list(data_parsed.keys())
    c1, c2 = st.columns([2, 1])
    with c1:
        loto = st.selectbox("🎰 Loto", lotos, key="ret_loto")
    with c2:
        top_n = st.number_input("Top N retards", min_value=5, max_value=90, value=20, key="ret_topn")

    tirages = data_parsed[loto]

    # Pour chaque numéro 1-90, retard = index du 1er tirage (récent) où il apparaît
    retards = {}
    for n in range(1, 91):
        retard = None
        for i, tir in enumerate(tirages):
            if n in nums_of(tir)[:5]:
                retard = i
                break
        retards[n] = retard if retard is not None else len(tirages)  # jamais sorti

    # Tri : plus grand retard en premier
    tri = sorted(retards.items(), key=lambda x: -x[1])

    # Top N retards
    st.markdown(f"**🥶 Top {int(top_n)} numéros les plus en retard :**")
    html = "<div style='display:flex;flex-wrap:wrap;gap:6px;margin:8px 0;'>"
    for n, r in tri[:int(top_n)]:
        # Couleur selon retard
        if r >= 30:   c = "#dc2626"   # rouge
        elif r >= 15: c = "#f97316"   # orange
        elif r >= 8:  c = "#eab308"   # jaune
        else:         c = "#22c55e"   # vert
        html += (f"<div style='background:{c};color:white;padding:8px 12px;border-radius:8px;"
                 f"min-width:60px;text-align:center;font-weight:bold;'>"
                 f"<div style='font-size:20px;'>{n}</div>"
                 f"<div style='font-size:11px;opacity:0.9;'>{r} tir.</div></div>")
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

    # Grille 1-90 complète
    st.markdown("**🎯 Grille 1-90 (chaleur des retards) :**")
    html = "<div style='display:grid;grid-template-columns:repeat(10,1fr);gap:4px;font-family:monospace;'>"
    for n in range(1, 91):
        r = retards[n]
        if r == 0:    c = "#3b82f6"   # bleu = sorti au dernier tirage
        elif r < 3:   c = "#06b6d4"   # cyan = tout récent
        elif r < 8:   c = "#22c55e"   # vert = normal
        elif r < 15:  c = "#eab308"   # jaune = attention
        elif r < 30:  c = "#f97316"   # orange = retard
        else:         c = "#dc2626"   # rouge = gros retard
        html += (f"<div style='background:{c};color:white;padding:6px;border-radius:5px;"
                 f"text-align:center;font-weight:bold;font-size:13px;'>"
                 f"{n}<div style='font-size:10px;opacity:0.85;'>{r}</div></div>")
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

    st.caption("🔵 sorti dernier tirage · 🟢 récent · 🟡 8-14 tir. · 🟠 15-29 tir. · 🔴 30+ tir.")


# ─────────────────────────────────────────────
# PAIRES & TRIPLETS
# ─────────────────────────────────────────────
def render_paires(data_parsed):
    st.subheader("🔗 Paires & Triplets")
    st.caption("Combinaisons de numéros qui sortent souvent ensemble.")

    lotos = list(data_parsed.keys())
    c1, c2, c3 = st.columns(3)
    with c1:
        loto = st.selectbox("🎰 Loto", lotos, key="pair_loto")
    with c2:
        nb_analyse = st.number_input("Nb tirages analysés", min_value=20, max_value=2000, value=200, key="pair_nb")
    with c3:
        top = st.number_input("Top affichés", min_value=10, max_value=100, value=30, key="pair_top")

    tirages = data_parsed[loto][:int(nb_analyse)]

    from itertools import combinations
    from collections import Counter

    paires = Counter()
    triplets = Counter()

    for tir in tirages:
        nums = sorted(nums_of(tir)[:5])
        for p in combinations(nums, 2):
            paires[p] += 1
        for t in combinations(nums, 3):
            triplets[t] += 1

    tabP, tabT = st.tabs(["🔗 Paires", "🎲 Triplets"])

    with tabP:
        st.markdown(f"**Top {int(top)} paires les plus fréquentes** (analysées : {len(tirages)} tirages)")
        html = "<div style='display:flex;flex-wrap:wrap;gap:8px;margin:8px 0;'>"
        for (a, b), cnt in paires.most_common(int(top)):
            # Couleur selon fréquence
            pct = (cnt / len(tirages)) * 100
            if pct >= 5:   c = "#dc2626"
            elif pct >= 3: c = "#f97316"
            elif pct >= 2: c = "#eab308"
            else:          c = "#3b82f6"
            html += (f"<div style='background:{c};color:white;padding:8px 12px;border-radius:8px;"
                     f"text-align:center;font-weight:bold;'>"
                     f"<div style='font-size:16px;'>{a} · {b}</div>"
                     f"<div style='font-size:11px;opacity:0.9;'>{cnt}× ({pct:.1f}%)</div></div>")
        html += "</div>"
        st.markdown(html, unsafe_allow_html=True)

    with tabT:
        st.markdown(f"**Top {int(top)} triplets les plus fréquents** (analysés : {len(tirages)} tirages)")
        html = "<div style='display:flex;flex-wrap:wrap;gap:8px;margin:8px 0;'>"
        for (a, b, c_), cnt in triplets.most_common(int(top)):
            pct = (cnt / len(tirages)) * 100
            if pct >= 2:    c = "#dc2626"
            elif pct >= 1:  c = "#f97316"
            elif pct >= 0.5:c = "#eab308"
            else:           c = "#3b82f6"
            html += (f"<div style='background:{c};color:white;padding:8px 12px;border-radius:8px;"
                     f"text-align:center;font-weight:bold;'>"
                     f"<div style='font-size:15px;'>{a} · {b} · {c_}</div>"
                     f"<div style='font-size:11px;opacity:0.9;'>{cnt}× ({pct:.1f}%)</div></div>")
        html += "</div>"
        st.markdown(html, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# TERMINAISONS (unités et dizaines)
# ─────────────────────────────────────────────
def render_terminaisons(data_parsed):
    st.subheader("🎯 Terminaisons — Analyse par unité/dizaine")
    st.caption("Grouper les numéros par terminaison (unité) ou par dizaine.")

    lotos = list(data_parsed.keys())
    c1, c2, c3 = st.columns(3)
    with c1:
        loto = st.selectbox("🎰 Loto", lotos, key="term_loto")
    with c2:
        nb = st.number_input("Nb tirages analysés", min_value=10, max_value=500, value=50, key="term_nb")
    with c3:
        mode = st.radio("Mode", ["Unité (0-9)", "Dizaine (0-8)"], key="term_mode")

    tirages = data_parsed[loto][:int(nb)]

    from collections import Counter
    compteur = Counter()
    for tir in tirages:
        for n in nums_of(tir)[:5]:
            if mode.startswith("Unité"):
                compteur[n % 10] += 1
            else:
                compteur[n // 10] += 1  # 0-8 (0=1-9, 8=80-89, 9 pour 90)

    # Rendu
    if mode.startswith("Unité"):
        st.markdown(f"**Répartition par unité (chiffre final)** sur {len(tirages)} tirages")
        groupes = {u: [n for n in range(1, 91) if n % 10 == u] for u in range(10)}
    else:
        st.markdown(f"**Répartition par dizaine** sur {len(tirages)} tirages")
        groupes = {d: [n for n in range(1, 91) if n // 10 == d] for d in range(10)}

    # Barres horizontales
    max_val = max(compteur.values()) if compteur else 1
    html = "<div style='font-family:monospace;'>"
    for k in sorted(groupes.keys()):
        if not groupes[k]:
            continue
        cnt = compteur.get(k, 0)
        pct = (cnt / max_val) * 100 if max_val else 0
        # Couleur selon fréquence
        if pct >= 80:   bar_c = "#dc2626"
        elif pct >= 60: bar_c = "#f97316"
        elif pct >= 40: bar_c = "#eab308"
        elif pct >= 20: bar_c = "#22c55e"
        else:           bar_c = "#3b82f6"

        # Label
        if mode.startswith("Unité"):
            label = f"...{k}"
            detail = ",".join(str(x) for x in groupes[k])
        else:
            if k == 0:
                label = "1-9"
            elif k == 9:
                label = "90"
            else:
                label = f"{k*10}-{k*10+9}"
            detail = ",".join(str(x) for x in groupes[k])

        html += (f"<div style='margin:6px 0;'>"
                 f"<div style='display:flex;justify-content:space-between;font-size:13px;color:#cbd5e1;'>"
                 f"<span><b>{label}</b> ({detail})</span>"
                 f"<span><b>{cnt}</b></span></div>"
                 f"<div style='background:#1e293b;border-radius:6px;overflow:hidden;height:22px;'>"
                 f"<div style='background:{bar_c};height:100%;width:{pct}%;transition:width 0.5s;'></div></div>"
                 f"</div>")
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# N COLLÉS — module unifié (Numéros / Terminaisons / Dizaines / Colonnes)
# ─────────────────────────────────────────────
def get_classes_of(num, type_class):
    """Retourne la ou les classes d'un numéro selon le type.
    Numéros: [num]. Terminaisons: [unité]. Dizaines: [dizaine].
    Colonnes: liste des chiffres contenus (ex: 34 → [3,4], 22 → [2])."""
    if type_class == "Numéros":
        return [num]
    if type_class == "Terminaisons":
        return [num % 10]
    if type_class == "Dizaines":
        return [num // 10]
    if type_class == "Colonnes":
        return sorted({int(c) for c in str(num)})
    return [num]

def label_classe(k, type_class):
    """Nom lisible d'une classe."""
    if type_class == "Numéros":      return str(k)
    if type_class == "Terminaisons": return f"…{k}"
    if type_class == "Dizaines":
        if k == 0: return "1-9"
        if k == 9: return "90"
        return f"{k*10}-{k*10+9}"
    if type_class == "Colonnes":     return f"chiffre {k}"
    return str(k)


def render_colles(data_parsed):
    st.subheader("🧷 N Collés — Numéros / Terminaisons / Dizaines / Colonnes")
    st.caption("Trouve les combinaisons qui sortent souvent ensemble, ou les tirages où plusieurs numéros de la même classe sortent.")

    lotos = list(data_parsed.keys())
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    with c1:
        loto = st.selectbox("🎰 Loto", lotos, key="col_loto")
    with c2:
        type_class = st.selectbox("🏷️ Type", ["Numéros", "Terminaisons", "Dizaines", "Colonnes"], key="col_type",
                                  help="Colonnes = numéros contenant tel chiffre (ex: 34 est dans colonne 3 ET colonne 4)")
    with c3:
        N = st.number_input("N (collés)", min_value=2, max_value=5, value=3, key="col_n")
    with c4:
        nb_analyse = st.number_input("Nb tirages", min_value=20, max_value=3000, value=300, key="col_nba")

    mode = st.radio(
        "🎛️ Mode d'analyse",
        ["🔥 Combos fréquentes (top des combinaisons de N classes)",
         "🎯 Concentration (tirages où ≥N numéros ont la même classe)"],
        key="col_mode", horizontal=False
    )

    tirages = data_parsed[loto][:int(nb_analyse)]

    # ═══ MODE A : Combos fréquentes ═══
    if mode.startswith("🔥"):
        from itertools import combinations
        from collections import Counter

        combos = Counter()
        for tir in tirages:
            nums = nums_of(tir)[:5]
            # Ensemble de classes présentes dans ce tirage
            classes_tir = set()
            for n in nums:
                for c in get_classes_of(n, type_class):
                    classes_tir.add(c)
            # Toutes les combinaisons de N classes
            for combo in combinations(sorted(classes_tir), int(N)):
                combos[combo] += 1

        top_n = st.slider("Top affichés", 10, 100, 30, key="col_top")
        st.markdown(f"**Top {top_n} combinaisons de {int(N)} {type_class.lower()}** — analysées : {len(tirages)} tirages")

        if not combos:
            st.warning("Pas assez de données.")
            return

        html = "<div style='display:flex;flex-wrap:wrap;gap:8px;margin:8px 0;'>"
        for combo, cnt in combos.most_common(top_n):
            pct = (cnt / len(tirages)) * 100
            if pct >= 20:  c = "#dc2626"
            elif pct >= 10: c = "#f97316"
            elif pct >= 5:  c = "#eab308"
            elif pct >= 2:  c = "#22c55e"
            else:           c = "#3b82f6"
            label = " · ".join(label_classe(k, type_class) for k in combo)
            html += (f"<div style='background:{c};color:white;padding:8px 12px;border-radius:8px;"
                     f"text-align:center;font-weight:bold;min-width:80px;'>"
                     f"<div style='font-size:15px;'>{label}</div>"
                     f"<div style='font-size:11px;opacity:0.9;'>{cnt}× ({pct:.1f}%)</div></div>")
        html += "</div>"
        st.markdown(html, unsafe_allow_html=True)

    # ═══ MODE B : Concentration dans un tirage ═══
    else:
        if type_class == "Numéros":
            st.info("💡 Le mode « Concentration » n'a pas de sens pour Numéros (les 5 numéros d'un tirage sont distincts). Utilise Terminaisons / Dizaines / Colonnes.")
            return

        max_show = st.slider("Nb tirages max affichés", 10, 200, 50, key="col_maxshow")

        st.markdown(f"**Tirages où ≥ {int(N)} numéros partagent la même {type_class[:-1].lower()}** — analysés : {len(tirages)} tirages")

        html = "<div style='font-family:monospace;font-size:14px;'>"
        html += ("<div style='display:grid;grid-template-columns:50px 1fr 160px;gap:10px;"
                 "font-weight:bold;padding:6px;border-bottom:2px solid #475569;'>"
                 "<div>#</div><div>Tirage</div><div>Classe(s) concentrée(s)</div></div>")

        count_hits = 0
        shown = 0
        for i, tir in enumerate(tirages):
            nums = nums_of(tir)[:5]
            # Compter par classe
            from collections import Counter
            comp = Counter()
            appartenance = {}  # {classe: [num, num, ...]}
            for n in nums:
                for c in get_classes_of(n, type_class):
                    comp[c] += 1
                    appartenance.setdefault(c, []).append(n)
            # Classes qui atteignent N
            classes_hit = [c for c, v in comp.items() if v >= int(N)]
            if not classes_hit:
                continue
            count_hits += 1
            if shown >= max_show:
                continue
            shown += 1
            # Numéros à surligner (ceux qui font partie d'une classe hit)
            nums_surligner = set()
            for c in classes_hit:
                for n in appartenance[c]:
                    nums_surligner.add(n)

            cells = ""
            for n in nums:
                if n in nums_surligner:
                    cells += (f"<span style='background:#f59e0b;color:#0f172a;padding:4px 9px;"
                              f"border-radius:6px;margin:2px;display:inline-block;font-weight:bold;"
                              f"box-shadow:0 0 6px rgba(245,158,11,0.6);'>{n}</span>")
                else:
                    cells += (f"<span style='background:#1e293b;color:#94a3b8;padding:4px 9px;"
                              f"border-radius:6px;margin:2px;display:inline-block;'>{n}</span>")

            # Badges classes
            badges = ""
            for c in classes_hit:
                badges += (f"<span style='background:#f59e0b;color:#0f172a;padding:3px 8px;"
                           f"border-radius:5px;margin:2px;display:inline-block;font-weight:bold;font-size:12px;'>"
                           f"{label_classe(c, type_class)} ({comp[c]})</span>")

            bg = "#0f172a" if i % 2 == 0 else "#020617"
            html += (f"<div style='display:grid;grid-template-columns:50px 1fr 160px;gap:10px;"
                     f"padding:6px;background:{bg};align-items:center;'>"
                     f"<div style='color:#64748b;'>{i+1}</div><div>{cells}</div><div>{badges}</div></div>")
        html += "</div>"
        st.markdown(html, unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            st.metric("Tirages avec concentration", f"{count_hits}/{len(tirages)}")
        with c2:
            pct = (count_hits / len(tirages)) * 100 if tirages else 0
            st.metric("Fréquence", f"{pct:.1f}%")


# ─────────────────────────────────────────────
# RECHERCHE Bk / Sure / Nap (avec ou sans position)
# ─────────────────────────────────────────────
def render_recherche_bsn(data_parsed):
    st.subheader("🎯 Recherche 1Bk / 2Sure / 3Nap / 4Nap / 5Nap")
    st.caption("Trouve les tirages contenant N numéros donnés (banker, sure, nap), avec ou sans position imposée.")

    lotos = list(data_parsed.keys())
    c1, c2 = st.columns([2, 1])
    with c1:
        cible = st.selectbox("🎰 Jeu(x)", ["📚 Tous les jeux"] + lotos, key="bsn_cible")
    with c2:
        mode = st.selectbox("Type de recherche", ["1 Bk", "2 Sure", "3 Nap", "4 Nap", "5 Nap"], key="bsn_mode")

    nb_num = int(mode.split()[0])

    st.markdown(f"**Saisir les {nb_num} numéros à rechercher** (0 = ignoré). Position : 0 = n'importe où, 1-5 = colonne fixe.")

    numeros = []
    positions = []
    cols = st.columns(nb_num)
    for i in range(nb_num):
        with cols[i]:
            n = st.number_input(f"N°{i+1}", min_value=0, max_value=90, value=0, key=f"bsn_n_{i}")
            p = st.number_input(f"Pos {i+1}", min_value=0, max_value=5, value=0, key=f"bsn_p_{i}",
                                help="0 = n'importe où, 1-5 = position fixe")
            if n > 0:
                numeros.append(int(n))
                positions.append(int(p))

    if len(numeros) < nb_num:
        st.warning(f"⚠️ Saisis les {nb_num} numéros pour lancer la recherche.")
        return

    if not st.button("🔍 Rechercher", type="primary", use_container_width=True, key="bsn_go"):
        return

    jeux = lotos if cible == "📚 Tous les jeux" else [cible]

    trouves = []  # {jeu, idx, nums, positions_trouvees}
    for jeu in jeux:
        for i, tir in enumerate(data_parsed[jeu]):
            nums = nums_of(tir)[:5]
            # Vérifier que tous les numéros sont présents et à la bonne position
            ok = True
            pos_utilisees = set()
            pos_trouvees = {}  # {num: index_position}
            for n, p in zip(numeros, positions):
                if p == 0:
                    # N'importe où, mais éviter double compte
                    trouve_pos = None
                    for k, v in enumerate(nums):
                        if v == n and k not in pos_utilisees:
                            trouve_pos = k
                            break
                    if trouve_pos is None:
                        ok = False
                        break
                    pos_utilisees.add(trouve_pos)
                    pos_trouvees[n] = trouve_pos
                else:
                    # Position fixe (p-1 en index)
                    if nums[p-1] != n or (p-1) in pos_utilisees:
                        ok = False
                        break
                    pos_utilisees.add(p-1)
                    pos_trouvees[n] = p-1
            if ok:
                trouves.append({'jeu': jeu, 'idx': i, 'nums': nums, 'pos': pos_trouvees, 'total': sum(nums)})

    if not trouves:
        st.warning("Aucun tirage trouvé avec cette combinaison.")
        return

    st.success(f"✅ {len(trouves)} tirage(s) trouvé(s)")

    par_page = st.selectbox("Résultats par page", [10, 25, 50, 100], index=1, key="bsn_pp")
    total_pages = (len(trouves) + par_page - 1) // par_page
    page = st.number_input(f"Page (1 à {total_pages})", min_value=1, max_value=max(1, total_pages), value=1, key="bsn_page")
    debut = (page - 1) * par_page
    fin = min(debut + par_page, len(trouves))

    html = "<div style='font-family:monospace;font-size:14px;'>"
    html += ("<div style='display:grid;grid-template-columns:130px 1fr 70px;gap:10px;"
             "font-weight:bold;padding:6px;border-bottom:2px solid #475569;'>"
             "<div>Jeu / #</div><div>Numéros</div><div>Total</div></div>")

    for r in trouves[debut:fin]:
        cells = ""
        num_trouves_set = set(r['pos'].values())
        for k, n in enumerate(r['nums']):
            if k in num_trouves_set:
                cells += (f"<span style='background:transparent;color:#22d3ee;padding:3px 8px;"
                          f"border:2px solid #22d3ee;border-radius:5px;margin:2px;display:inline-block;"
                          f"font-weight:bold;'>{n}</span>")
            else:
                cells += (f"<span style='background:#1e293b;color:#e2e8f0;padding:3px 8px;"
                          f"border-radius:5px;margin:2px;display:inline-block;'>{n}</span>")
        bg = "#0f172a"
        html += (f"<div style='display:grid;grid-template-columns:130px 1fr 70px;gap:10px;"
                 f"padding:6px;background:{bg};align-items:center;'>"
                 f"<div style='color:#94a3b8;'>{r['jeu']} #{r['idx']+1}</div>"
                 f"<div>{cells}</div>"
                 f"<div style='color:#64748b;'>{r['total']}</div></div>")
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# SOMME HORIZONTALE (recherche par total)
# ─────────────────────────────────────────────
def render_somme(data_parsed):
    st.subheader("📐 Somme horizontale — Recherche par total")
    st.caption("Trouve les tirages avec tel total. Options : dessus/dessous, suivi de totalité.")

    lotos = list(data_parsed.keys())
    c1, c2 = st.columns([2, 1])
    with c1:
        cible = st.selectbox("🎰 Jeu(x)", ["📚 Tous les jeux"] + lotos, key="som_cible")
    with c2:
        mode = st.selectbox("Mode", ["Total exact", "Plage [min-max]"], key="som_mode")

    if mode == "Total exact":
        c1, c2 = st.columns(2)
        with c1:
            total_cible = st.number_input("Total recherché", min_value=15, max_value=450, value=200, key="som_tc")
        with c2:
            tolerance = st.number_input("Tolérance ±", min_value=0, max_value=50, value=0, key="som_tol")
        t_min, t_max = int(total_cible) - int(tolerance), int(total_cible) + int(tolerance)
    else:
        c1, c2 = st.columns(2)
        with c1:
            t_min = st.number_input("Total min", min_value=15, max_value=450, value=180, key="som_min")
        with c2:
            t_max = st.number_input("Total max", min_value=15, max_value=450, value=220, key="som_max")
        t_min, t_max = int(t_min), int(t_max)

    st.markdown("**Options complémentaires :**")
    c1, c2, c3 = st.columns(3)
    with c1:
        opt_dessus = st.checkbox("↑ Total = numéro DESSUS", key="som_od",
                                 help="Le total apparaît dans le tirage plus récent (dessus)")
    with c2:
        opt_dessous = st.checkbox("↓ Total = numéro DESSOUS", key="som_ob",
                                  help="Le total apparaît dans le tirage plus ancien (dessous)")
    with c3:
        opt_meme = st.checkbox("🔵 Total DANS le tirage même", key="som_om")

    if not st.button("🔍 Rechercher", type="primary", use_container_width=True, key="som_go"):
        return

    jeux = lotos if cible == "📚 Tous les jeux" else [cible]

    trouves = []
    for jeu in jeux:
        tirs = data_parsed[jeu]
        for i, tir in enumerate(tirs):
            nums = nums_of(tir)[:5]
            total = sum(nums)
            if not (t_min <= total <= t_max):
                continue

            # Filtres options
            if opt_meme and (total not in nums):
                continue
            nums_dessus = nums_of(tirs[i-1])[:5] if i > 0 else None
            nums_dessous = nums_of(tirs[i+1])[:5] if i+1 < len(tirs) else None
            if opt_dessus and (nums_dessus is None or total not in nums_dessus):
                continue
            if opt_dessous and (nums_dessous is None or total not in nums_dessous):
                continue

            trouves.append({
                'jeu': jeu, 'idx': i, 'nums': nums, 'total': total,
                'nums_dessus': nums_dessus, 'nums_dessous': nums_dessous
            })

    if not trouves:
        st.warning("Aucun tirage trouvé.")
        return

    st.success(f"✅ {len(trouves)} tirage(s) trouvé(s)")

    par_page = st.selectbox("Résultats par page", [10, 25, 50], index=1, key="som_pp")
    total_pages = (len(trouves) + par_page - 1) // par_page
    page = st.number_input(f"Page (1 à {total_pages})", min_value=1, max_value=max(1, total_pages), value=1, key="som_page")
    debut = (page - 1) * par_page
    fin = min(debut + par_page, len(trouves))

    show_context = st.checkbox("Afficher tirage dessus/dessous", value=(opt_dessus or opt_dessous), key="som_ctx")

    for r in trouves[debut:fin]:
        html = f"<div style='background:#1e40af;color:white;padding:6px 10px;border-radius:6px 6px 0 0;font-weight:bold;'>{r['jeu']} #{r['idx']+1} — Total {r['total']}</div>"
        html += "<div style='background:#0f172a;padding:8px;border-radius:0 0 6px 6px;font-family:monospace;font-size:14px;'>"

        # Dessus
        if show_context and r['nums_dessus']:
            hi = (opt_dessus and r['total'] in r['nums_dessus'])
            cells = ""
            for n in r['nums_dessus']:
                if hi and n == r['total']:
                    cells += f"<span style='background:transparent;color:#22c55e;padding:3px 8px;border:2px solid #22c55e;border-radius:5px;margin:2px;display:inline-block;font-weight:bold;'>{n}</span>"
                else:
                    cells += f"<span style='background:#1e293b;color:#94a3b8;padding:3px 8px;border-radius:5px;margin:2px;display:inline-block;'>{n}</span>"
            html += f"<div style='padding:4px;color:#64748b;font-size:12px;'>↑ Dessus (#{r['idx']}) : {cells}</div>"

        # Ligne principale
        cells = ""
        for n in r['nums']:
            if opt_meme and n == r['total']:
                cells += f"<span style='background:transparent;color:#3b82f6;padding:3px 8px;border:2px solid #3b82f6;border-radius:5px;margin:2px;display:inline-block;font-weight:bold;'>{n}</span>"
            else:
                cells += f"<span style='background:#1e293b;color:#e2e8f0;padding:3px 8px;border-radius:5px;margin:2px;display:inline-block;font-weight:bold;'>{n}</span>"
        tot_html = f"<span style='background:#f97316;color:white;padding:3px 10px;border-radius:5px;font-weight:bold;'>Tot {r['total']}</span>"
        html += f"<div style='padding:5px;background:#020617;border-radius:4px;'>{cells} &nbsp; {tot_html}</div>"

        # Dessous
        if show_context and r['nums_dessous']:
            hi = (opt_dessous and r['total'] in r['nums_dessous'])
            cells = ""
            for n in r['nums_dessous']:
                if hi and n == r['total']:
                    cells += f"<span style='background:transparent;color:#eab308;padding:3px 8px;border:2px solid #eab308;border-radius:5px;margin:2px;display:inline-block;font-weight:bold;'>{n}</span>"
                else:
                    cells += f"<span style='background:#1e293b;color:#94a3b8;padding:3px 8px;border-radius:5px;margin:2px;display:inline-block;'>{n}</span>"
            html += f"<div style='padding:4px;color:#64748b;font-size:12px;'>↓ Dessous (#{r['idx']+2}) : {cells}</div>"

        html += "</div>"
        st.markdown(html, unsafe_allow_html=True)
        st.markdown("")


# ─────────────────────────────────────────────
# SUPERPOSITION (verticale : numéro dessus/dessous)
# ─────────────────────────────────────────────
def render_superposition(data_parsed):
    st.subheader("↕️ Superposition — Numéro Dessus/Dessous")
    st.caption("Trouve les cas où un numéro A est juste au-dessus ou en-dessous d'un numéro B dans les tirages consécutifs.")

    lotos = list(data_parsed.keys())
    c1, c2 = st.columns([2, 1])
    with c1:
        cible = st.selectbox("🎰 Jeu(x)", ["📚 Tous les jeux"] + lotos, key="sup_cible")
    with c2:
        sens = st.selectbox("Sens", ["A DESSUS de B (A plus récent)", "A DESSOUS de B (A plus ancien)"], key="sup_sens")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        num_A = st.number_input("Numéro A", min_value=1, max_value=90, value=1, key="sup_a")
    with c2:
        pos_A = st.number_input("Position A", min_value=0, max_value=5, value=0, key="sup_pa",
                                help="0 = n'importe où, 1-5 = colonne fixe")
    with c3:
        num_B = st.number_input("Numéro B", min_value=1, max_value=90, value=2, key="sup_b")
    with c4:
        pos_B = st.number_input("Position B", min_value=0, max_value=5, value=0, key="sup_pb",
                                help="0 = n'importe où, 1-5 = colonne fixe")

    pos_variable = st.checkbox("🔗 Position variable (A et B à la MÊME position, mais laquelle importe peu)",
                               value=False, key="sup_pv",
                               help="Si coché : A et B doivent être à la même colonne. Sinon : positions indépendantes.")

    if not st.button("🔍 Rechercher", type="primary", use_container_width=True, key="sup_go"):
        return

    jeux = lotos if cible == "📚 Tous les jeux" else [cible]

    def check_position(nums, num, pos):
        """Vérifie qu'un numéro est présent à la position demandée. Retourne l'index ou None."""
        if pos == 0:
            return nums.index(num) if num in nums else None
        return pos-1 if (pos-1 < len(nums) and nums[pos-1] == num) else None

    trouves = []  # {jeu, idx_A, idx_B, nums_A, nums_B}

    for jeu in jeux:
        tirs = data_parsed[jeu]
        # data_parsed[jeu][0] = plus récent, [-1] = plus ancien
        # "A dessus de B" = A plus récent que B = idx_A < idx_B (idx_A = idx_B - 1 pour consécutif)
        for i in range(len(tirs) - 1):
            nums_recent = nums_of(tirs[i])[:5]      # plus récent
            nums_ancien = nums_of(tirs[i+1])[:5]    # plus ancien (juste dessous)

            if sens.startswith("A DESSUS"):
                # A dans nums_recent (dessus), B dans nums_ancien (dessous)
                idx_A_pos = check_position(nums_recent, int(num_A), int(pos_A))
                idx_B_pos = check_position(nums_ancien, int(num_B), int(pos_B))
                idx_recent, idx_ancien = i, i+1
            else:
                # A dans nums_ancien (dessous), B dans nums_recent (dessus)
                idx_A_pos = check_position(nums_ancien, int(num_A), int(pos_A))
                idx_B_pos = check_position(nums_recent, int(num_B), int(pos_B))
                idx_recent, idx_ancien = i, i+1

            if idx_A_pos is None or idx_B_pos is None:
                continue

            # Si position variable, exiger même position
            if pos_variable and idx_A_pos != idx_B_pos:
                continue

            trouves.append({
                'jeu': jeu,
                'idx_recent': idx_recent, 'nums_recent': nums_recent,
                'idx_ancien': idx_ancien, 'nums_ancien': nums_ancien,
                'idx_A_pos': idx_A_pos, 'idx_B_pos': idx_B_pos,
                'sens_A_dessus': sens.startswith("A DESSUS")
            })

    if not trouves:
        st.warning("Aucune superposition trouvée.")
        return

    st.success(f"✅ {len(trouves)} superposition(s) trouvée(s)")

    par_page = st.selectbox("Résultats par page", [10, 25, 50], index=0, key="sup_pp")
    total_pages = (len(trouves) + par_page - 1) // par_page
    page = st.number_input(f"Page (1 à {total_pages})", min_value=1, max_value=max(1, total_pages), value=1, key="sup_page")
    debut = (page - 1) * par_page
    fin = min(debut + par_page, len(trouves))

    for r in trouves[debut:fin]:
        html = f"<div style='background:#7c2d12;color:white;padding:6px 10px;border-radius:6px 6px 0 0;font-weight:bold;'>{r['jeu']}</div>"
        html += "<div style='background:#0f172a;padding:8px;border-radius:0 0 6px 6px;font-family:monospace;font-size:14px;'>"

        # Ligne du dessus (plus récent)
        cells = ""
        surligne_pos = r['idx_A_pos'] if r['sens_A_dessus'] else r['idx_B_pos']
        surligne_color = "#22c55e" if r['sens_A_dessus'] else "#f43f5e"
        for k, n in enumerate(r['nums_recent']):
            if k == surligne_pos:
                cells += f"<span style='background:transparent;color:{surligne_color};padding:3px 8px;border:2px solid {surligne_color};border-radius:5px;margin:2px;display:inline-block;font-weight:bold;'>{n}</span>"
            else:
                cells += f"<span style='background:#1e293b;color:#e2e8f0;padding:3px 8px;border-radius:5px;margin:2px;display:inline-block;'>{n}</span>"
        html += f"<div style='padding:5px;background:#020617;border-radius:4px;margin-bottom:2px;'><span style='color:#94a3b8;font-size:11px;'>↑ #{r['idx_recent']+1}</span> &nbsp; {cells}</div>"

        # Ligne du dessous (plus ancien)
        cells = ""
        surligne_pos = r['idx_B_pos'] if r['sens_A_dessus'] else r['idx_A_pos']
        surligne_color = "#f43f5e" if r['sens_A_dessus'] else "#22c55e"
        for k, n in enumerate(r['nums_ancien']):
            if k == surligne_pos:
                cells += f"<span style='background:transparent;color:{surligne_color};padding:3px 8px;border:2px solid {surligne_color};border-radius:5px;margin:2px;display:inline-block;font-weight:bold;'>{n}</span>"
            else:
                cells += f"<span style='background:#1e293b;color:#e2e8f0;padding:3px 8px;border-radius:5px;margin:2px;display:inline-block;'>{n}</span>"
        html += f"<div style='padding:5px;background:#020617;border-radius:4px;'><span style='color:#94a3b8;font-size:11px;'>↓ #{r['idx_ancien']+1}</span> &nbsp; {cells}</div>"

        html += "</div>"
        st.markdown(html, unsafe_allow_html=True)
        st.markdown("")


# ─────────────────────────────────────────────
# ANALYSE D'UN NUMÉRO (un seul, avec ou sans position)
# ─────────────────────────────────────────────
def render_numero(data_parsed):
    st.subheader("🔎 Analyse d'un numéro")
    st.caption("Voir toutes les apparitions d'un seul numéro, partout ou à une position fixe.")

    lotos = list(data_parsed.keys())
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    with c1:
        cible = st.selectbox("🎰 Jeu(x)", ["📚 Tous les jeux"] + lotos, key="num_cible")
    with c2:
        num = st.number_input("Numéro", min_value=1, max_value=90, value=1, key="num_n")
    with c3:
        pos = st.number_input("Position", min_value=0, max_value=5, value=0, key="num_p",
                              help="0 = partout, 1-5 = colonne fixe")
    with c4:
        nb_max = st.number_input("Max affichés", min_value=20, max_value=1000, value=100, key="num_max")

    jeux = lotos if cible == "📚 Tous les jeux" else [cible]

    # Recherche
    apparitions = []  # {jeu, idx, nums, pos_trouvee, total}
    for jeu in jeux:
        tirs = data_parsed[jeu]
        for i, tir in enumerate(tirs):
            nums = nums_of(tir)[:5]
            if int(pos) == 0:
                # Partout
                if int(num) in nums:
                    apparitions.append({
                        'jeu': jeu, 'idx': i, 'nums': nums,
                        'pos_trouvee': nums.index(int(num)),
                        'total': sum(nums)
                    })
            else:
                # Position fixe
                p = int(pos) - 1
                if p < len(nums) and nums[p] == int(num):
                    apparitions.append({
                        'jeu': jeu, 'idx': i, 'nums': nums,
                        'pos_trouvee': p,
                        'total': sum(nums)
                    })

    if not apparitions:
        st.warning(f"Aucune apparition du numéro **{int(num)}** trouvée avec ces critères.")
        return

    # ═══ STATS ═══
    total_tirages = sum(len(data_parsed[j]) for j in jeux)
    freq_pct = (len(apparitions) / total_tirages) * 100 if total_tirages else 0

    # Retard actuel (index de la 1ère apparition dans le jeu le plus récent)
    if cible != "📚 Tous les jeux":
        premiere = min((a['idx'] for a in apparitions if a['jeu'] == cible), default=None)
        retard = premiere if premiere is not None else len(data_parsed[cible])
    else:
        retard = "—"

    # Position préférée (histogramme 5 slots)
    from collections import Counter
    pos_counter = Counter(a['pos_trouvee'] for a in apparitions)

    # Intervalles entre apparitions (par jeu)
    intervalles_moyens = {}
    for jeu in jeux:
        idxs = sorted([a['idx'] for a in apparitions if a['jeu'] == jeu])
        if len(idxs) >= 2:
            diffs = [idxs[i+1] - idxs[i] for i in range(len(idxs)-1)]
            intervalles_moyens[jeu] = sum(diffs) / len(diffs)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("🎯 Apparitions", len(apparitions))
    with c2:
        st.metric("📊 Fréquence", f"{freq_pct:.1f}%")
    with c3:
        st.metric("⏱️ Retard actuel", retard)
    with c4:
        if intervalles_moyens:
            moy = sum(intervalles_moyens.values()) / len(intervalles_moyens)
            st.metric("↔️ Intervalle moyen", f"{moy:.1f}")
        else:
            st.metric("↔️ Intervalle moyen", "—")

    # Histogramme des positions
    if int(pos) == 0:
        st.markdown("**📍 Positions préférées** (colonne 1 à 5) :")
        max_p = max(pos_counter.values()) if pos_counter else 1
        html = "<div style='display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin:8px 0;'>"
        for p in range(5):
            cnt = pos_counter.get(p, 0)
            pct = (cnt / max_p) * 100 if max_p else 0
            barh = int(60 * (cnt / max_p)) if max_p else 0
            html += (f"<div style='text-align:center;'>"
                     f"<div style='height:70px;display:flex;align-items:flex-end;justify-content:center;'>"
                     f"<div style='background:#3b82f6;width:60%;height:{barh}px;border-radius:4px 4px 0 0;'></div></div>"
                     f"<div style='background:#1e293b;color:white;padding:4px;border-radius:0 0 6px 6px;font-weight:bold;'>"
                     f"N{p+1}<br><span style='font-size:12px;color:#93c5fd;'>{cnt}</span></div></div>")
        html += "</div>"
        st.markdown(html, unsafe_allow_html=True)

    # ═══ JOURNAL ═══
    st.markdown(f"**📖 Journal ({len(apparitions)} apparitions, affichage de {min(int(nb_max), len(apparitions))})** — plus récent en haut")

    html = "<div style='font-family:monospace;font-size:14px;'>"
    html += ("<div style='display:grid;grid-template-columns:130px 1fr 70px 70px;gap:10px;"
             "font-weight:bold;padding:6px;border-bottom:2px solid #475569;'>"
             "<div>Jeu / #</div><div>Numéros</div><div>Pos</div><div>Total</div></div>")

    for a in apparitions[:int(nb_max)]:
        cells = ""
        for k, n in enumerate(a['nums']):
            if k == a['pos_trouvee']:
                cells += (f"<span style='background:#fbbf24;color:#0f172a;padding:3px 8px;"
                          f"border-radius:5px;margin:2px;display:inline-block;font-weight:bold;"
                          f"box-shadow:0 0 6px rgba(251,191,36,0.6);'>{n}</span>")
            else:
                cells += (f"<span style='background:#1e293b;color:#e2e8f0;padding:3px 8px;"
                          f"border-radius:5px;margin:2px;display:inline-block;'>{n}</span>")
        bg = "#0f172a"
        html += (f"<div style='display:grid;grid-template-columns:130px 1fr 70px 70px;gap:10px;"
                 f"padding:6px;background:{bg};align-items:center;'>"
                 f"<div style='color:#94a3b8;'>{a['jeu']} #{a['idx']+1}</div>"
                 f"<div>{cells}</div>"
                 f"<div style='color:#fbbf24;font-weight:bold;'>N{a['pos_trouvee']+1}</div>"
                 f"<div style='color:#64748b;'>{a['total']}</div></div>")
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# MODE EXCEL — tableau compact avec colonnes figées
# ─────────────────────────────────────────────
def render_par_annees(data_parsed, loto):
    """Même jeu, colonnes par année côte à côte (comme l'ancienne app)."""
    tirages = data_parsed[loto]

    # Regrouper par année (extrait de la date jj/mm/aaaa)
    by_year = {}
    for t in tirages:
        d = date_of(t)
        annee = d[-4:] if len(d) >= 4 and d[-4:].isdigit() else "????"
        by_year.setdefault(annee, []).append(t)

    annees_dispo = sorted([a for a in by_year.keys() if a != "????"], reverse=True)
    if not annees_dispo:
        st.warning("Pas de dates exploitables pour ce loto.")
        return

    # Sélecteur rapide : 3 / 5 / 10 / All
    c1, c2 = st.columns([1, 3])
    with c1:
        quick = st.radio("Années :", ["3", "5", "10", "All"], horizontal=True, key="pa_quick")
    nb_q = len(annees_dispo) if quick == "All" else int(quick)
    with c2:
        annees_sel = st.multiselect("Ou choisis précisément :", annees_dispo,
                                    default=annees_dispo[:min(nb_q, len(annees_dispo))],
                                    key="pa_annees")
    if not annees_sel:
        annees_sel = annees_dispo[:nb_q]

    # Palette de couleurs d'en-tête par colonne (comme l'ancienne app)
    palette = ["#0f766e", "#7c2d12", "#3f6212", "#1e1b4b", "#7f1d1d", "#164e63",
               "#713f12", "#4a044e", "#052e16", "#1e3a8a"]

    st.caption(f"**{loto}** — {len(annees_sel)} année(s) côte à côte, plus récente à gauche.")

    cols = st.columns(len(annees_sel))
    for ci, annee in enumerate(annees_sel):
        with cols[ci]:
            tirs = by_year.get(annee, [])
            head_bg = palette[ci % len(palette)]
            html = (f"<div style='background:{head_bg};color:white;padding:8px;border-radius:8px 8px 0 0;"
                    f"text-align:center;font-weight:bold;font-size:15px;'>{loto} {annee}"
                    f"<div style='font-size:11px;font-weight:normal;'>{len(tirs)} tirages</div></div>")
            # en-tête colonnes
            html += ("<div style='background:#1e293b;color:#e2e8f0;display:grid;"
                     "grid-template-columns:32px 30px repeat(5,1fr) 32px;gap:1px;"
                     "font-size:10px;font-weight:bold;padding:3px 2px;'>"
                     "<div>N°</div><div>DATE</div><div>N1</div><div>N2</div><div>N3</div><div>N4</div><div>N5</div><div>TOT</div></div>")
            html += "<div style='font-family:monospace;font-size:11px;border:1px solid #334155;border-top:none;border-radius:0 0 8px 8px;overflow:hidden;'>"
            for i, t in enumerate(tirs):
                nums = nums_of(t)[:5]
                tot = total_of(t)
                if tot < 150: tot_bg, tot_fg = "#dcfce7", "#166534"
                elif tot < 250: tot_bg, tot_fg = "#fef9c3", "#854d0e"
                elif tot < 300: tot_bg, tot_fg = "#ffedd5", "#9a3412"
                else: tot_bg, tot_fg = "#fecaca", "#991b1b"
                bg = "#f8fafc" if i % 2 == 0 else "#fff7ed"
                cells = "".join(f"<div style='text-align:center;font-weight:bold;color:#0f172a;'>{n}</div>" for n in nums)
                html += (f"<div style='display:grid;grid-template-columns:32px 30px repeat(5,1fr) 32px;gap:1px;"
                         f"padding:2px;background:{bg};align-items:center;'>"
                         f"<div style='color:{head_bg};font-weight:bold;font-size:10px;'>{num_of(t)}</div>"
                         f"<div style='color:#64748b;font-size:9px;'>{date_of(t)[:5]}</div>"
                         f"{cells}"
                         f"<div style='background:{tot_bg};color:{tot_fg};text-align:center;font-weight:bold;"
                         f"font-size:10px;border-radius:3px;padding:1px;'>{tot}</div></div>")
            html += "</div>"
            st.markdown(html, unsafe_allow_html=True)

    # Légende
    st.markdown("🟢 <150 &nbsp; 🟡 150-249 &nbsp; 🟠 250-299 &nbsp; 🔴 ≥300", unsafe_allow_html=True)


def render_pickin_oblique(data_parsed):
    """Pickin | Oblique : les numéros des N derniers tirages du loto A réapparaissent
    en vertical/oblique sur des lignes consécutives du loto B."""
    st.subheader("🔀 Pickin | Oblique")
    st.caption("Cherche où les numéros de la référence (loto A) réapparaissent en vertical/oblique "
               "sur lignes consécutives dans le loto B. Jaune = correspondance.")

    lotos = sorted(data_parsed.keys())
    c1, c2 = st.columns(2)
    with c1:
        loto_a = st.selectbox("🎰 Loto A (référence)", lotos, key="po_a")
    with c2:
        max_num = max((num_of(t) for t in data_parsed[loto_a]), default=1)
        excl = st.number_input("Exclure à partir du tirage", min_value=2, max_value=max_num + 1,
                               value=max_num + 1, key="po_excl",
                               help="La référence = les N tirages juste avant ce numéro")

    c3, c4, c5, c6 = st.columns(4)
    with c3:
        nb_ref = st.selectbox("Nombre de lignes (référence)", [2, 3, 4, 5], key="po_nbref")
    with c4:
        mode_pos = st.selectbox("Position", ["Vertical + oblique (±1)", "Vertical seul", "Libre (toute position)"], key="po_mode")
    with c5:
        inverse = st.checkbox("Recherche inversée", key="po_inv",
                              help="Motif dans l'ordre inverse (dernière ligne réf en premier)")
    with c6:
        nb_apres = st.number_input("Lignes après la référence", min_value=0, max_value=5, value=2, key="po_apres")

    loto_b = st.selectbox("🎰 Loto B (cible)", lotos,
                          index=min(1, len(lotos)-1), key="po_b")

    if st.button("🔄 Actualiser", type="primary", use_container_width=True, key="po_go"):
        # ── Référence : les nb_ref tirages juste avant 'excl' (ordre chronologique) ──
        t_a = data_parsed[loto_a]  # récent en premier
        ref_chrono = [t for t in reversed(t_a) if num_of(t) < excl][-int(nb_ref):]
        if len(ref_chrono) < int(nb_ref):
            st.error("Pas assez de tirages avant ce numéro.")
            return
        if inverse:
            ref_chrono = list(reversed(ref_chrono))
        ref_sets = [set(nums_of(t)) for t in ref_chrono]

        st.markdown("**Référence :** " + " → ".join(
            f"<span style='background:#1e3a8a;color:white;padding:2px 8px;border-radius:5px;font-family:monospace;'>"
            f"N°{num_of(t)} : {' '.join(map(str, nums_of(t)))}</span>"
            for t in ref_chrono), unsafe_allow_html=True)

        # ── Cible en ordre chronologique ──
        t_b = list(reversed(data_parsed[loto_b]))  # index 0 = T1 (le plus ancien)
        n_lignes = int(nb_ref)
        matches = []  # (index_debut, {(ligne_offset, position)})
        for j in range(len(t_b) - n_lignes + 1):
            # chaîner : num de ref[0] en ligne j à pos p0, num de ref[1] ligne j+1 à p0±1, etc.
            chemins = []
            nums0 = nums_of(t_b[j])
            for p, n in enumerate(nums0):
                if n in ref_sets[0]:
                    chemins.append([(0, p)])
            for k in range(1, n_lignes):
                nouveaux = []
                nums_k = nums_of(t_b[j + k])
                for chemin in chemins:
                    _, prev_p = chemin[-1]
                    if mode_pos.startswith("Vertical +"):
                        positions = range(max(0, prev_p - 1), min(len(nums_k), prev_p + 2))
                    elif mode_pos.startswith("Vertical seul"):
                        positions = [prev_p] if prev_p < len(nums_k) else []
                    else:  # Libre
                        positions = range(len(nums_k))
                    for p in positions:
                        if nums_k[p] in ref_sets[k]:
                            nouveaux.append(chemin + [(k, p)])
                chemins = nouveaux
                if not chemins:
                    break
            if chemins:
                cells = set()
                for chemin in chemins:
                    for k, p in chemin:
                        cells.add((k, p))
                matches.append((j, cells))

        st.session_state["po_result"] = (matches, loto_b, int(nb_apres), n_lignes)

    # ── Affichage des résultats ──
    if "po_result" in st.session_state:
        matches, loto_b_r, nb_apres_r, n_lignes_r = st.session_state["po_result"]
        if loto_b_r != loto_b:
            return
        t_b = list(reversed(data_parsed[loto_b]))
        st.markdown(f"### Résultat ({len(matches)})")
        if not matches:
            st.info("Aucune correspondance trouvée.")
            return

        labels = [f"T{j+1}" for j, _ in matches]
        sel = st.radio("Correspondances :", labels, horizontal=True, key="po_sel")
        idx = labels.index(sel)
        j0, cells = matches[idx]

        # Zone : 5 lignes avant, le motif, nb_apres lignes après
        debut = max(0, j0 - 5)
        fin = min(len(t_b), j0 + n_lignes_r + nb_apres_r + 5)
        st.markdown(f"**{loto_b} T {debut+1} - {fin}**")

        html = "<div style='font-family:monospace;font-size:12px;'>"
        html += ("<div style='display:grid;grid-template-columns:36px 46px 40px repeat(5,1fr) 44px;gap:1px;"
                 "font-weight:bold;padding:3px;border-bottom:2px solid #475569;'>"
                 "<div>L</div><div>D</div><div>Y</div><div>D1</div><div>D2</div><div>D3</div><div>D4</div><div>D5</div><div>To</div></div>")
        for j in range(debut, fin):
            t = t_b[j]
            nums = nums_of(t)[:5]
            d = date_of(t)
            dd, yy = (d[:5], d[6:]) if len(d) >= 10 else (d, "")
            k = j - j0
            in_motif = 0 <= k < n_lignes_r
            cells_html = ""
            for p, n in enumerate(nums):
                if in_motif and (k, p) in cells:
                    cells_html += f"<div style='background:#fde047;color:#0f172a;text-align:center;font-weight:bold;border-radius:3px;'>{n}</div>"
                else:
                    cells_html += f"<div style='text-align:center;color:#e2e8f0;'>{n}</div>"
            apres = n_lignes_r <= k < n_lignes_r + nb_apres_r
            bg = "#1e3a5f" if in_motif else ("#14532d" if apres else ("#0f172a" if j % 2 == 0 else "#020617"))
            html += (f"<div style='display:grid;grid-template-columns:36px 46px 40px repeat(5,1fr) 44px;gap:1px;"
                     f"padding:2px;background:{bg};align-items:center;'>"
                     f"<div style='color:#0ea5e9;font-weight:bold;'>{j+1}</div>"
                     f"<div style='color:#94a3b8;font-size:10px;'>{dd}</div>"
                     f"<div style='color:#64748b;font-size:10px;'>{yy}</div>"
                     f"{cells_html}"
                     f"<div style='color:#cbd5e1;text-align:center;font-size:11px;'>{total_of(t)}</div></div>")
        html += "</div>"
        st.markdown(html, unsafe_allow_html=True)
        st.caption("🟦 Zone du motif (jaune = numéros trouvés) · 🟩 Lignes après la référence")


def render_mode_excel(data_parsed):
    st.subheader("📊 Mode Excel — Vue tabulaire")

    lotos = list(data_parsed.keys())

    # ═══ 4 VARIANTES ═══
    c1, c2, c3, c4, c5 = st.columns([2, 1, 1, 1, 1])
    with c1:
        loto = st.selectbox("🎰 Loto", lotos, key="excel_loto")
    with c2:
        opt_excel = st.checkbox("☐ Excel", value=True, key="excel_opt_normal",
                                help="Mode tableau normal avec filtres avancés")
    with c3:
        opt_freeze = st.checkbox("📊 fige 1 re col", value=False, key="excel_opt_freeze",
                                 help="Colonnes figées : la colonne '#' reste fixe lors du scroll")
    with c4:
        opt_compare = st.checkbox("🎮 Comparer jeux", value=False, key="excel_opt_compare",
                                  help="Affichage multi-jeux côte à côte")
    with c5:
        opt_annees = st.checkbox("📅 Par années", value=False, key="excel_opt_annees",
                                 help="Le même jeu, colonnes par année côte à côte")

    # ═══ MODE : PAR ANNÉES ═══
    if opt_annees:
        render_par_annees(data_parsed, loto)
        return

    # ═══ MODE : EXCEL NORMAL OU FIGÉ ═══
    if opt_excel or opt_freeze:
        limit = st.number_input("Nb tirages (max)", min_value=50, max_value=5000, value=500, key="excel_limit")
        tirages = data_parsed[loto][:int(limit)]

        rows = []
        for i, tir in enumerate(tirages):
            nums = nums_of(tir)[:5]
            total = sum(nums)
            rows.append({
                "#": i + 1,
                "N1": nums[0] if len(nums) > 0 else "",
                "N2": nums[1] if len(nums) > 1 else "",
                "N3": nums[2] if len(nums) > 2 else "",
                "N4": nums[3] if len(nums) > 3 else "",
                "N5": nums[4] if len(nums) > 4 else "",
                "Total": total,
                "Min": min(nums) if nums else "",
                "Max": max(nums) if nums else "",
                "Écart": (max(nums) - min(nums)) if nums else "",
            })
        df = pd.DataFrame(rows)

        with st.expander("🔍 Filtres avancés"):
            c1, c2, c3 = st.columns(3)
            with c1:
                t_min = st.number_input("Total min", value=int(df["Total"].min()) if len(df) else 0, key="excel_tmin")
                t_max = st.number_input("Total max", value=int(df["Total"].max()) if len(df) else 450, key="excel_tmax")
            with c2:
                contient_num = st.number_input("Contient le numéro (0=aucun)", min_value=0, max_value=90, value=0, key="excel_cnum")
                contient_num2 = st.number_input("ET contient aussi (0=aucun)", min_value=0, max_value=90, value=0, key="excel_cnum2")
            with c3:
                ecart_min = st.number_input("Écart min", value=0, key="excel_ecmin")
                ecart_max = st.number_input("Écart max", value=90, key="excel_ecmax")

        df_f = df.copy()
        df_f = df_f[(df_f["Total"] >= t_min) & (df_f["Total"] <= t_max)]
        df_f = df_f[(df_f["Écart"] >= ecart_min) & (df_f["Écart"] <= ecart_max)]
        for num_filter in [contient_num, contient_num2]:
            if num_filter > 0:
                mask = ((df_f["N1"] == num_filter) | (df_f["N2"] == num_filter) | (df_f["N3"] == num_filter) |
                        (df_f["N4"] == num_filter) | (df_f["N5"] == num_filter))
                df_f = df_f[mask]

        st.caption(f"**{len(df_f)}** tirages affichés (sur {len(df)}).")

        if opt_freeze:
            # ═══ MODE FIGÉ ALIGNÉ : # figé à gauche, N1-N5 + TOTAL COLLÉ alignés ═══
            st.markdown(f"<div style='color:#22c55e;font-size:12px;margin-bottom:8px;'>✅ Mode aligné : # figé | N1-N5 alignés | Total collé aux résultats</div>", unsafe_allow_html=True)
            W_NUM = 54
            W_B = 52
            W_TOT = 62
            # Header + rows en grille unique : # | N1 N2 N3 N4 N5 | TOTAL collé | Min Max
            html = f"<div style='font-family:monospace;font-size:13px;overflow-x:auto;'>"
            html += f"<div style='display:grid;grid-template-columns:{W_NUM}px repeat(5,{W_B}px) {W_TOT}px 50px 50px;gap:3px;padding:6px 4px;background:#0f172a;font-weight:bold;border-bottom:2px solid #475569;position:sticky;top:0;z-index:10;'>"
            html += f"<div style='text-align:center;'>#</div>"
            for col in ["N1","N2","N3","N4","N5"]:
                html += f"<div style='text-align:center;'>{col}</div>"
            html += f"<div style='text-align:center;color:#fbbf24;margin-left:6px;border-left:2px solid #334155;padding-left:6px;'>Total</div>"
            html += f"<div style='text-align:center;color:#64748b;'>Min</div><div style='text-align:center;color:#64748b;'>Max</div>"
            html += f"</div>"
            for _, row in df_f.iterrows():
                val_tot = int(row["Total"]) if pd.notna(row["Total"]) else 0
                if val_tot < 150: c = "#22c55e"
                elif val_tot < 250: c = "#eab308"
                elif val_tot < 300: c = "#f97316"
                else: c = "#ef4444"
                bg_row = "#0f172a" if int(row['#'])%2==0 else "#020617"
                html += f"<div style='display:grid;grid-template-columns:{W_NUM}px repeat(5,{W_B}px) {W_TOT}px 50px 50px;gap:3px;padding:4px;background:{bg_row};align-items:center;'>"
                html += f"<div style='text-align:center;color:#0ea5e9;font-weight:bold;'>{int(row['#'])}</div>"
                for col in ["N1","N2","N3","N4","N5"]:
                    v = int(row[col]) if pd.notna(row[col]) else ""
                    html += f"<div style='background:#1e293b;color:#e2e8f0;padding:4px 0;text-align:center;border-radius:5px;font-weight:bold;'>{v}</div>"
                html += f"<div style='background:{c};color:white;padding:4px 0;text-align:center;border-radius:5px;font-weight:900;margin-left:6px;border-left:2px solid #0f172a;'>{val_tot}</div>"
                html += f"<div style='text-align:center;color:#64748b;font-size:11px;'>{int(row['Min']) if pd.notna(row['Min']) else ''}</div>"
                html += f"<div style='text-align:center;color:#64748b;font-size:11px;'>{int(row['Max']) if pd.notna(row['Max']) else ''}</div>"
                html += f"</div>"
            html += f"</div>"
            st.markdown(html, unsafe_allow_html=True)
        else:
            # ═══ MODE EXCEL NORMAL ═══
            st.dataframe(
                df_f, use_container_width=True, height=600, hide_index=True,
                column_config={
                    "#": st.column_config.NumberColumn("#", width="small"),
                    "N1": st.column_config.NumberColumn("N1", width="small"),
                    "N2": st.column_config.NumberColumn("N2", width="small"),
                    "N3": st.column_config.NumberColumn("N3", width="small"),
                    "N4": st.column_config.NumberColumn("N4", width="small"),
                    "N5": st.column_config.NumberColumn("N5", width="small"),
                    "Total": st.column_config.NumberColumn("Total", width="small"),
                }
            )

        csv = df_f.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Exporter CSV", data=csv, file_name=f"{loto}_export.csv",
                           mime='text/csv', use_container_width=True)

    # ═══ MODE : COMPARER JEUX (côte à côte) ═══
    if opt_compare:
        st.markdown("---")
        c1, c2 = st.columns([3, 1])
        with c1:
            jeux_sel = st.multiselect(
                "🎮 Jeux à comparer (côte à côte)",
                lotos,
                default=lotos[:min(3, len(lotos))],
                key="excel_compare_jeux"
            )
        with c2:
            nb_lignes = st.number_input("Nb lignes/jeu", min_value=10, max_value=200, value=30, key="excel_compare_nb")

        if not jeux_sel:
            st.info("Sélectionne au moins un jeu.")
            return

        st.caption(f"**{len(jeux_sel)}** jeux affichés côte à côte, {int(nb_lignes)} derniers tirages chacun.")

        cols = st.columns(len(jeux_sel))
        for c_idx, jeu in enumerate(jeux_sel):
            with cols[c_idx]:
                st.markdown(f"<div style='background:#22d3ee;color:#0f172a;padding:6px 10px;border-radius:6px 6px 0 0;font-weight:bold;text-align:center;'>{jeu}</div>", unsafe_allow_html=True)
                tirs = data_parsed[jeu][:int(nb_lignes)]
                html = "<div style='background:#0f172a;padding:4px;border-radius:0 0 6px 6px;font-family:monospace;font-size:12px;'>"
                html += "<div style='display:grid;grid-template-columns:30px 1fr 40px;gap:4px;font-weight:bold;color:#94a3b8;padding:3px;border-bottom:1px solid #334155;'><div>#</div><div>Nums</div><div>Tot</div></div>"
                for i, tir in enumerate(tirs):
                    nums = nums_of(tir)[:5]
                    total = sum(nums)
                    cells = "".join(f"<span style='background:#1e293b;color:#e2e8f0;padding:1px 4px;border-radius:3px;margin:1px;display:inline-block;'>{n}</span>" for n in nums)
                    if total < 150: ct = "#22c55e"
                    elif total < 250: ct = "#eab308"
                    elif total < 300: ct = "#f97316"
                    else: ct = "#ef4444"
                    bg = "#020617" if i % 2 == 0 else "#0f172a"
                    html += (f"<div style='display:grid;grid-template-columns:30px 1fr 40px;gap:4px;padding:3px;background:{bg};align-items:center;'>"
                             f"<div style='color:#64748b;'>{i+1}</div>"
                             f"<div>{cells}</div>"
                             f"<div style='background:{ct};color:white;padding:1px 4px;border-radius:3px;text-align:center;font-size:11px;font-weight:bold;'>{total}</div></div>")
                html += "</div>"
                st.markdown(html, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# PRONOSTICS AVANCÉS (3 stratégies)
# ─────────────────────────────────────────────
def render_pronostics_v2(data_parsed):
    st.subheader("🎯 Pronostics — 3 stratégies")
    st.caption("Génère des picks selon 3 stratégies : Équilibré (mix chauds/retards), Chauds (numéros fréquents), Retards (numéros absents).")

    lotos = list(data_parsed.keys())
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        loto = st.selectbox("🎰 Loto", lotos, key="pro_loto")
    with c2:
        nb_analyse = st.number_input("Tirages analysés", min_value=20, max_value=1000, value=100, key="pro_nba")
    with c3:
        nb_picks = st.number_input("Nb de picks à générer", min_value=1, max_value=20, value=5, key="pro_nbp")

    tirages = data_parsed[loto][:int(nb_analyse)]

    # Analyse : fréquence, retard, dernier tirage
    from collections import Counter
    freq = Counter()
    for tir in tirages:
        for n in nums_of(tir)[:5]:
            freq[n] += 1

    # Retards
    retards = {}
    for n in range(1, 91):
        retard = len(tirages)  # défaut : jamais sorti
        for i, tir in enumerate(tirages):
            if n in nums_of(tir)[:5]:
                retard = i
                break
        retards[n] = retard

    # Numéros chauds (top fréquence)
    chauds = [n for n, _ in freq.most_common(25)]
    # Numéros retards (plus grand retard)
    retard_sorted = sorted(retards.items(), key=lambda x: -x[1])
    retards_top = [n for n, _ in retard_sorted[:25]]

    import random

    st.markdown("---")
    tab_eq, tab_ch, tab_re = st.tabs(["⚖️ Équilibré", "🔥 Chauds", "🥶 Retards"])

    def render_pick_block(picks_list, titre, color, bankers, strat_key=""):
        st.markdown(f"**{titre}**")
        for i, pick in enumerate(picks_list, 1):
            cells = ""
            for n in sorted(pick):
                cells += (f"<span style='background:{color};color:white;padding:5px 12px;"
                          f"border-radius:6px;margin:2px;display:inline-block;font-weight:bold;'>{n}</span>")
            total = sum(pick)
            col_a, col_b = st.columns([5, 1])
            with col_a:
                html = (f"<div style='background:#0f172a;padding:8px;border-radius:6px;margin:4px 0;"
                        f"display:flex;justify-content:space-between;align-items:center;'>"
                        f"<div><span style='color:#64748b;'>#{i}</span> &nbsp; {cells}</div>"
                        f"<div style='color:#94a3b8;font-size:13px;'>Total: <b>{total}</b></div></div>")
                st.markdown(html, unsafe_allow_html=True)
            with col_b:
                if st.button("💾", key=f"savepick_{strat_key}_{i}", help="Sauvegarder ce pronostic pour suivi"):
                    add_prediction(loto, titre, sorted(pick))
                    st.success("Sauvegardé !")
        # Bankers
        st.markdown(f"**🎯 Bankers suggérés** (basés sur cette stratégie) :")
        b_html = ""
        for b in bankers:
            b_html += (f"<span style='background:transparent;color:{color};padding:5px 12px;"
                       f"border:2px solid {color};border-radius:6px;margin:3px;display:inline-block;font-weight:bold;'>{b}</span>")
        st.markdown(f"<div>{b_html}</div>", unsafe_allow_html=True)

    with tab_eq:
        # 3 chauds + 2 retards
        picks = []
        for _ in range(int(nb_picks)):
            pick = random.sample(chauds[:15], min(3, len(chauds))) + random.sample(retards_top[:20], min(2, len(retards_top)))
            picks.append(pick)
        bankers = list(dict.fromkeys(chauds[:5] + retards_top[:3]))[:8]
        render_pick_block(picks, "Picks Équilibrés (3 chauds + 2 retards)", "#22c55e", bankers, strat_key="eq")

    with tab_ch:
        picks = []
        for _ in range(int(nb_picks)):
            pick = random.sample(chauds[:20], 5)
            picks.append(pick)
        bankers = chauds[:8]
        render_pick_block(picks, "Picks Chauds (top fréquence)", "#f97316", bankers, strat_key="ch")

    with tab_re:
        picks = []
        for _ in range(int(nb_picks)):
            pick = random.sample(retards_top[:25], 5)
            picks.append(pick)
        bankers = retards_top[:8]
        render_pick_block(picks, "Picks Retards (numéros absents)", "#3b82f6", bankers, strat_key="re")

    st.markdown("---")
    st.caption(f"📊 Analyse basée sur les {len(tirages)} derniers tirages de **{loto}**.")

    # ═══ SUIVI DES PRONOSTICS SAUVEGARDÉS (comme Oracle du Loto) ═══
    st.markdown("---")
    all_preds = load_predictions()
    loto_preds = all_preds.get(loto, [])
    with st.expander(f"📋 Mes pronostics sauvegardés pour {loto} ({len(loto_preds)})", expanded=bool(loto_preds)):
        if not loto_preds:
            st.caption("Aucun pronostic sauvegardé pour ce loto. Clique 💾 à côté d'un pick ci-dessus pour en garder trace.")
        else:
            # tirages indexés par date pour vérifier les résultats une fois le tirage réel disponible
            tirages_par_date = {}
            for t in data_parsed[loto]:
                d = date_of(t)
                if d:
                    tirages_par_date.setdefault(d, t)
            for i, p in enumerate(reversed(loto_preds)):
                real_idx = len(loto_preds) - 1 - i
                nums_txt = ", ".join(str(n) for n in p["numbers"])
                actual = tirages_par_date.get(p["date"])
                c1, c2, c3 = st.columns([3, 2, 1])
                with c1:
                    st.markdown(f"**{p['strategie']}** — {nums_txt} <span style='color:#94a3b8;font-size:12px;'>({p['date']})</span>", unsafe_allow_html=True)
                with c2:
                    if actual:
                        hits = len(set(p["numbers"]) & set(nums_of(actual)[:5]))
                        color = "#22c55e" if hits >= 2 else "#64748b"
                        st.markdown(f"<span style='color:{color};font-weight:bold;'>{hits}/5 numéros trouvés</span>", unsafe_allow_html=True)
                    else:
                        st.caption("en attente du tirage")
                with c3:
                    if st.button("🗑️", key=f"delpred_{loto}_{real_idx}"):
                        delete_prediction(loto, real_idx)
                        st.rerun()


# ─────────────────────────────────────────────
# RECHERCHE AVANCÉE — Comparaison 2 Plans + Dérivés
# ─────────────────────────────────────────────
def render_recherche_avancee(data_parsed):
    st.subheader("🔍 Recherche Avancée — Comparaison Plans")
    st.caption("Compare 2 combinaisons (plans) et affiche les dérivés (Counter, Bonanza, Malta, etc.)")

    lotos = list(data_parsed.keys())

    # Sélection du contexte
    c1, c2 = st.columns([3, 1])
    with c1:
        loto = st.selectbox("🎰 Loto", lotos, key="rech_loto")
    with c2:
        mode = st.selectbox("📊 Mode", ["Comparaison 2 plans", "Par années"], key="rech_mode")

    if mode == "Comparaison 2 plans":
        st.markdown("**Saisis 2 plans (combinaisons de 5 numéros) et clique pour voir les dérivés**")
        
        c1, c2 = st.columns(2)
        with c1:
            plan1_txt = st.text_input("Plan 1", placeholder="Ex: 13 31 42 55 67", key="rech_p1")
        with c2:
            plan2_txt = st.text_input("Plan 2", placeholder="Ex: 7 24 56 78 89", key="rech_p2")

        if st.button("🔍 Analyser & Chercher", type="primary", use_container_width=True, key="rech_go"):
            try:
                nums1 = [int(x.strip()) for x in plan1_txt.split()][:5]
                nums2 = [int(x.strip()) for x in plan2_txt.split()][:5]
                
                if len(nums1) == 5 and len(nums2) == 5:
                    # Affichage plans côte à côte
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown(f"<div style='background:#1e40af;color:white;padding:8px;border-radius:6px;text-align:center;font-weight:bold;'>Plan 1 : {' '.join(map(str, nums1))}</div>", unsafe_allow_html=True)
                        # Affichage dérivés Plan 1
                        deriv1 = get_classifications(nums1[0]) if len(nums1) > 0 else {}
                        html = "<div style='background:#0f172a;padding:10px;border-radius:6px;margin-top:6px;font-family:monospace;font-size:13px;'>"
                        for key in ['counter', 'bonanza', 'malta', 'key', 'turning', 'partner', 'shadow', 'code', 'equiv', 'mirror']:
                            val = deriv1.get(key, 'N/A')
                            html += f"<div style='padding:4px;border-bottom:1px solid #1e293b;'><span style='color:#94a3b8;'>{key.capitalize()}:</span> <span style='color:#22d3ee;font-weight:bold;'>{val}</span></div>"
                        html += "</div>"
                        st.markdown(html, unsafe_allow_html=True)
                    
                    with col2:
                        st.markdown(f"<div style='background:#065f46;color:white;padding:8px;border-radius:6px;text-align:center;font-weight:bold;'>Plan 2 : {' '.join(map(str, nums2))}</div>", unsafe_allow_html=True)
                        # Affichage dérivés Plan 2
                        deriv2 = get_classifications(nums2[0]) if len(nums2) > 0 else {}
                        html = "<div style='background:#0f172a;padding:10px;border-radius:6px;margin-top:6px;font-family:monospace;font-size:13px;'>"
                        for key in ['counter', 'bonanza', 'malta', 'key', 'turning', 'partner', 'shadow', 'code', 'equiv', 'mirror']:
                            val = deriv2.get(key, 'N/A')
                            html += f"<div style='padding:4px;border-bottom:1px solid #1e293b;'><span style='color:#94a3b8;'>{key.capitalize()}:</span> <span style='color:#22d3ee;font-weight:bold;'>{val}</span></div>"
                        html += "</div>"
                        st.markdown(html, unsafe_allow_html=True)
                    
                    # Recherche dans les tirages
                    st.markdown("---")
                    st.markdown("**Tirages correspondants :**")
                    tirages = data_parsed[loto]
                    matches = []
                    for i, tir in enumerate(tirages):
                        tir_nums = nums_of(tir)[:5]
                        # Chercher si les numéros correspondent
                        if any(n in tir_nums for n in nums1) or any(n in tir_nums for n in nums2):
                            matches.append((i, tir_nums, sum(tir_nums)))
                    
                    if matches:
                        st.success(f"✅ {len(matches)} tirage(s) correspondant(s)")
                        for idx, n, tot in matches[:20]:
                            cells = "".join(f"<span style='background:#1e293b;color:#e2e8f0;padding:3px 8px;border-radius:5px;margin:2px;display:inline-block;'>{n}</span>" for n in n)
                            st.markdown(f"<div style='background:#020617;padding:6px;border-radius:5px;margin:4px 0;'>{idx+1} : {cells} <span style='color:#64748b;'>Tot: {tot}</span></div>", unsafe_allow_html=True)
                    else:
                        st.info("Aucun tirage correspondant")
                else:
                    st.error("⚠️ Chaque plan doit avoir 5 numéros")
            except:
                st.error("Format invalide. Ex: 13 31 42 55 67")

    else:  # Par années
        st.markdown("**Comparaison année par année**")
        annee = st.slider("Année", 2015, 2026, 2026, key="rech_annee")
        
        # Simple version : affiche les tirages de l'année
        tirages = data_parsed[loto]
        # Filtrer par année (approximatif, basé sur index)
        st.info("Feature disponible en v21 avec dates précises")


# ─────────────────────────────────────────────
# APP PRINCIPALE
# ─────────────────────────────────────────────
# 1) Charger depuis le cache JSON
data_parsed = {}
for loto_name in list_cached_lotos():
    if loto_name.startswith("_"):
        continue
    cached_data = load_cache(loto_name)
    if cached_data:
        data_parsed[loto_name] = cached_data

# 2) Nouveau loto ajouté via le bouton "➕ Ajouter un loto"
if "pending_new_loto" in st.session_state:
    nom, f = st.session_state.pop("pending_new_loto")
    tirages, result = parse_excel(f, nom)
    if tirages:
        data_parsed[nom] = tirages
        save_cache(nom, tirages)
        st.sidebar.success(f"✅ {nom} : {result} tirages (en cache)")
    else:
        st.sidebar.error(f"❌ {nom} : {result}")

# 3) Fichiers uploadés → parse + mise en cache (remplace le cache existant)
for loto_name, file in uploaded_data.items():
    tirages, result = parse_excel(file, loto_name)
    if tirages:
        data_parsed[loto_name] = tirages
        save_cache(loto_name, tirages)
        st.sidebar.info(f"✅ {loto_name} : {result} tirages (mis en cache)")
    else:
        st.sidebar.error(f"❌ {loto_name} : {result}")

# ═══ ➕ AJOUTER UN TIRAGE (mise à jour rapide) ═══
if data_parsed:
    with st.sidebar.expander("➕ Ajouter un tirage"):
        aj_loto = st.selectbox("Loto", sorted(data_parsed.keys()), key="aj_loto")
        aj_date = st.text_input("Date (jj/mm/aaaa)", placeholder="Ex: 11/07/2026", key="aj_date")
        aj_nums = st.text_input("Numéros (espace)", placeholder="Ex: 33 35 36 13 31", key="aj_nums")
        aj_machine = st.text_input("Machine (optionnel)", placeholder="Ex: 5 12 44 67 89", key="aj_machine")
        if st.button("💾 Enregistrer le tirage", key="aj_btn", use_container_width=True):
            try:
                nums = [int(x) for x in aj_nums.split() if x.strip().isdigit()]
                machine = [int(x) for x in aj_machine.split() if x.strip().isdigit()] if aj_machine.strip() else []
                if len(nums) >= 5:
                    dernier_num = max((num_of(t) for t in data_parsed[aj_loto]), default=0)
                    nouveau = {
                        'num': dernier_num + 1,
                        'date': aj_date.strip(),
                        'p': nums[:5],
                        'm': machine if machine else nums[5:],
                        'tot': sum(nums[:5])
                    }
                    # insérer en tête (plus récent en premier)
                    data_parsed[aj_loto].insert(0, nouveau)
                    save_cache(aj_loto, data_parsed[aj_loto])
                    st.success(f"✅ Tirage {nouveau['num']} ajouté à {aj_loto} !")
                else:
                    st.error("Au moins 5 numéros requis")
            except Exception as e:
                st.error(f"Erreur : {e}")

    # ═══ 🗑️ GESTION DU CACHE ═══
    with st.sidebar.expander("🗑️ Gérer le cache"):
        del_loto = st.selectbox("Loto à supprimer du cache", ["—"] + sorted(data_parsed.keys()), key="del_loto")
        if st.button("Supprimer", key="del_btn") and del_loto != "—":
            (CACHE_DIR / f"{del_loto}.json").unlink(missing_ok=True)
            st.success(f"🗑️ {del_loto} supprimé — recharge la page")

if len(data_parsed) > 0:
    st.sidebar.success(f"✅ {len(data_parsed)} loto(s) disponible(s)")

    if len(data_parsed) >= 2:
        tab_nav, tab_excel, tab1, tab_align, tab_3p, tab_po, tab_tot, tab_rt, tab_seq, tab_suit, tab_retard, tab_pair, tab_term, tab_col, tab_bsn, tab_som, tab_sup, tab_rech_avancee, tab2, tab3, tab4, tab5 = st.tabs([
            "📋 Navigation", "📊 Mode Excel", "🎨 Classifications", "🔀 Alignement", "🔀 3 Plages", "🔀 Pickin|Oblique", "🔢 Totaux", "🔍 Rech. Totaux", "🧬 Séquence",
            "🔢 Suites", "⏱️ Retards", "🔗 Paires", "🎯 Terminaisons", "🧷 N Collés",
            "🎯 Bk/Sure/Nap", "📐 Somme", "↕️ Superposition", "🔍 Rech. Avancée",
            "📊 Comparaisons", "🔁 Personnalisée", "🎯 Pronostics", "📈 Stats"
        ])

        with tab_nav:
            render_navigation(data_parsed)

        with tab_excel:
            render_mode_excel(data_parsed)

        with tab1:
            render_grille_classifications()

        with tab_align:
            render_alignement(data_parsed)

        with tab_3p:
            render_3plages(data_parsed)

        with tab_po:
            render_pickin_oblique(data_parsed)

        with tab_tot:
            render_totaux(data_parsed)

        with tab_rt:
            render_recherche_totaux(data_parsed)

        with tab_seq:
            render_sequence(data_parsed)

        with tab_suit:
            render_suites(data_parsed)

        with tab_retard:
            render_retards(data_parsed)

        with tab_pair:
            render_paires(data_parsed)

        with tab_term:
            render_terminaisons(data_parsed)

        with tab_col:
            render_colles(data_parsed)

        with tab_bsn:
            render_recherche_bsn(data_parsed)

        with tab_som:
            render_somme(data_parsed)

        with tab_sup:
            render_superposition(data_parsed)

        with tab_rech_avancee:
            render_recherche_avancee(data_parsed)

        with tab2:
            st.subheader("Comparer Tous")
            if st.button("🚀 LANCER", type="primary", use_container_width=True):
                with st.spinner("Analyse..."):
                    lotos_list = list(data_parsed.items())
                    results = []
                    for i in range(len(lotos_list)):
                        for j in range(i + 1, len(lotos_list)):
                            nom1, tir1 = lotos_list[i]
                            nom2, tir2 = lotos_list[j]
                            try:
                                l1 = [nums_of(t) for t in tir1]
                                l2 = [nums_of(t) for t in tir2]
                                comp = comparer_deux_lotos(l1, l2, nom1, nom2)
                                results.append({'Paire': f"{nom1} vs {nom2}", 'Similitudes': comp['nb_similitudes'], 'Score': comp['meilleur_score']})
                            except:
                                pass
                    if results:
                        results.sort(key=lambda x: x['Similitudes'], reverse=True)
                        st.dataframe(pd.DataFrame(results), use_container_width=True)
                        st.success(f"✅ {len(results)} paires !")
                    else:
                        st.warning("Pas de similitudes trouvées")

        with tab3:
            col1, col2 = st.columns(2)
            with col1:
                loto1 = st.selectbox("Loto 1", list(data_parsed.keys()))
            with col2:
                loto2 = st.selectbox("Loto 2", list(data_parsed.keys()), index=1 if len(data_parsed) > 1 else 0)
            if loto1 != loto2 and st.button("🔀 COMPARER", use_container_width=True):
                l1 = [nums_of(t) for t in data_parsed[loto1]]
                l2 = [nums_of(t) for t in data_parsed[loto2]]
                comp = comparer_deux_lotos(l1, l2, loto1, loto2)
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Similitudes", comp['nb_similitudes'])
                with col2:
                    st.metric("Score", f"{comp['meilleur_score']:.0f}")
                with col3:
                    st.metric("Tirages", f"{len(data_parsed[loto1])} vs {len(data_parsed[loto2])}")

        with tab4:
            all_tirages = []
            for tir in data_parsed.values():
                all_tirages.extend(nums_of(t) for t in tir)
            nb_picks = st.slider("Picks", 1, 15, 9)
            if st.button("🎯 GÉNÉRER", type="primary", use_container_width=True):
                picks = generer_pronostics(all_tirages, nb_picks)
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.write("**PICKS**")
                    for i, p in enumerate(picks['pronostics'][:nb_picks], 1):
                        st.code(f"{i}: {' '.join(map(str, p))}")
                with col2:
                    st.write("**BANKERS**")
                    st.code(str(picks['bankers']))
                with col3:
                    st.write("**HOT NUMS**")
                    st.code(str(picks['hot_numbers'][:10]))

        with tab5:
            stats = []
            for loto, tir in data_parsed.items():
                flat = [n for t in tir for n in nums_of(t)]
                totaux = [total_of(t) for t in tir]
                stats.append({
                    'Loto': loto,
                    'Tirages': len(tir),
                    'Min': min(flat), 'Max': max(flat),
                    'Moy num': f"{np.mean(flat):.1f}",
                    'Total moy': f"{np.mean(totaux):.0f}",
                    'Total min': min(totaux), 'Total max': max(totaux)
                })
            st.dataframe(pd.DataFrame(stats), use_container_width=True)

    else:
        st.warning(f"⚠️ Charge au moins 2 (actuellement {len(data_parsed)})")

else:
    # Même sans données chargées, on peut montrer la grille de classifications
    st.info("📁 Upload les fichiers Excel pour débloquer comparaisons et stats.")
    st.markdown("---")
    render_grille_classifications()
