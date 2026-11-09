#!/bin/bash
# Déploiement GOODLUCK IMMO INVEST : contrôle -> copie -> commit -> push (subtree) vers
# le dépôt GitHub dédié et privé "goodluck-immo-invest" (distinct de forecast-loto / pr-vision-loto).
# Usage :   ./deploy_goodluck.sh                (message automatique avec la date)
#           ./deploy_goodluck.sh "Mon message"  (message personnalisé)
# S'arrête dès qu'une vérification échoue (rien n'est poussé dans ce cas).

REPO_ROOT="${REPO_ROOT:-/Users/follyvitettegah/Desktop/SAUVEGARDE MULTIJEUX 1ER}"
SRC="${SRC:-$REPO_ROOT/GoodLuck Immo Invest - MAJ Conge}"
DEST="${DEST:-$REPO_ROOT/GOODLUCK A DEPLOYER}"
FILES=("index.html")
MSG="${1:-MAJ Goodluck Immo Invest $(date '+%d/%m/%Y %H:%M')}"
REMOTE="goodluck"
BRANCH="main"

echo "1/5  Contrôle des fichiers..."
cd "$SRC" || { echo "ERREUR : dossier source introuvable"; exit 1; }
for f in "${FILES[@]}"; do
  if [ ! -f "$SRC/$f" ]; then echo "ERREUR : $f introuvable dans $SRC"; exit 1; fi
done
if ! grep -q "<html" "$SRC/index.html" || ! grep -q "</html>" "$SRC/index.html"; then
  echo "ERREUR : index.html ne ressemble pas à un document HTML valide, rien n'est poussé."
  exit 1
fi
echo "     OK."

echo "2/5  Copie vers le dossier de déploiement..."
for f in "${FILES[@]}"; do
  cp "$SRC/$f" "$DEST/$f" || exit 1
done
for f in "${FILES[@]}"; do
  diff -q "$SRC/$f" "$DEST/$f" >/dev/null || { echo "ERREUR : copie différente pour $f"; exit 1; }
done
echo "     copies identiques."

if [ -n "$DRY_RUN" ]; then echo "Mode essai : pas de commit ni de push."; exit 0; fi

echo "3/5  Commit..."
cd "$REPO_ROOT" || exit 1
git add "GOODLUCK A DEPLOYER/index.html"
if git diff --cached --quiet; then
  echo "     Rien de nouveau à envoyer (déjà à jour)."
  exit 0
fi
git commit -m "$MSG" || exit 1

echo "4/5  Vérification du remote..."
if ! git remote get-url "$REMOTE" >/dev/null 2>&1; then
  echo "ERREUR : remote '$REMOTE' introuvable. Lancez une fois :"
  echo "  git remote add $REMOTE https://github.com/huegbo/goodluck-immo-invest.git"
  exit 1
fi

echo "5/5  Push (subtree) vers $REMOTE/$BRANCH..."
git subtree push --prefix="GOODLUCK A DEPLOYER" "$REMOTE" "$BRANCH" || { echo "ERREUR : le push a échoué."; exit 1; }
echo "OK : poussé vers goodluck-immo-invest. Recharge le site dans 1 à 2 minutes."
