def comparer_deux_lotos(tir1, tir2, nom1, nom2, nb_lignes=3, min_communs=1):
    nb_sim = 0
    score_max = 0.0
    
    tir1_sample = tir1[-nb_lignes:] if len(tir1) > nb_lignes else tir1
    tir2_sample = tir2[-nb_lignes:] if len(tir2) > nb_lignes else tir2
    
    for t1 in tir1_sample:
        for t2 in tir2_sample:
            communs = len(set(t1) & set(t2))
            if communs >= min_communs:
                nb_sim += 1
                score = (communs / max(len(set(t1)), len(set(t2)))) * 100
                score_max = max(score_max, score)
    
    return {
        'nb_similitudes': nb_sim,
        'meilleur_score': score_max,
        'nom1': nom1,
        'nom2': nom2
    }
