#!/bin/bash
# Déploiement GOODLUCK IMMO INVEST : contrôle -> copie -> commit -> push.
# Usage :   ./deploy_goodluck.sh                (message automatique avec la date)
#           ./deploy_goodluck.sh "Mon message"  (message personnalisé)
# S'arrête dès qu'une vérification échoue (rien n'est poussé dans ce cas).

SRC="${SRC:-/Users/follyvitettegah/Desktop/SAUVEGARDE MULTIJEUX 1ER/GoodLuck Immo Invest - MAJ Conge}"
DEST="${DEST:-/Users/follyvitettegah/Desktop/SAUVEGARDE MULTIJEUX 1ER/GOODLUCK A DEPLOYER}"
FILES=("index.html")
MSG="${1:-MAJ Goodluck Immo Invest $(date '+%d/%m/%Y %H:%M')}"

echo "1/4  Contrôle des fichiers..."
cd "$SRC" || { echo "ERREUR : dossier source introuvable"; exit 1; }
for f in "${FILES[@]}"; do
  if [ ! -f "$SRC/$f" ]; then echo "ERREUR : $f introuvable dans $SRC"; exit 1; fi
done
# Vérification basique de la validité HTML (balises ouvrantes/fermantes de base présentes)
if ! grep -q "<html" "$SRC/index.html" || ! grep -q "</html>" "$SRC/index.html"; then
  echo "ERREUR : index.html ne ressemble pas à un document HTML valide, rien n'est poussé."
  exit 1
fi
echo "     OK."

echo "2/4  Copie vers le dossier de déploiement..."
for f in "${FILES[@]}"; do
  cp "$SRC/$f" "$DEST/$f" || exit 1
done
for f in "${FILES[@]}"; do
  diff -q "$SRC/$f" "$DEST/$f" >/dev/null || { echo "ERREUR : copie différente pour $f"; exit 1; }
done
echo "     copies identiques."

if [ -n "$DRY_RUN" ]; then echo "Mode essai : pas de commit ni de push."; exit 0; fi

echo "3/4  Commit..."
cd "$DEST" || exit 1
git add "${FILES[@]}"
if git diff --cached --quiet; then
  echo "     Rien de nouveau à envoyer (déjà à jour)."
  exit 0
fi
git commit -m "$MSG" || exit 1

echo "4/4  Push..."
git push || { echo "ERREUR : le push a échoué."; exit 1; }
echo "OK : poussé. Recharge le site dans 1 à 2 minutes."
