from collections import Counter
import random

def detecter_bankers(historique, top=8):
    flat = [n for tir in historique for n in tir]
    freq = Counter(flat)
    return [num for num, _ in freq.most_common(top)]

def generer_pronostics(historique, nombre_picks=9):
    flat = [n for tir in historique for n in tir]
    freq = Counter(flat)
    hot = [num for num, _ in freq.most_common(20)]
    cold = [n for n in range(1, 91) if n not in hot]
    
    picks = []
    for _ in range(nombre_picks):
        pick = sorted(random.sample(hot[:15], min(3, len(hot))) + random.sample(cold[:30], min(2, len(cold))))
        picks.append(pick)
    
    return {
        'pronostics': picks,
        'hot_numbers': hot,
        'bankers': detecter_bankers(historique, top=8)
    }
