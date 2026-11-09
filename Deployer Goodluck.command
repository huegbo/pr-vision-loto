#!/bin/bash
# Double-clic : lance le déploiement de Goodluck Immo Invest (fonctionne depuis n'importe quel dossier).
cd "/Users/follyvitettegah/Desktop/SAUVEGARDE MULTIJEUX 1ER" || { echo "ERREUR : dossier introuvable"; read -n 1 -s -r -p "Appuie sur une touche."; exit 1; }
./deploy_goodluck.sh
echo ""
read -n 1 -s -r -p "Terminé. Appuie sur une touche pour fermer cette fenêtre."
# Ferme automatiquement cette fenêtre Terminal (évite l'accumulation de fenêtres)
MYTTY="$(tty)"
osascript >/dev/null 2>&1 <<OSA &
tell application "Terminal"
  repeat with w in windows
    try
      if (tty of selected tab of w) is "$MYTTY" then close w saving no
    end try
  end repeat
end tell
OSA
exit 0
