// Cloudflare Pages Function — proxy sécurisé vers l'API Claude (Anthropic).
// La clé API (ANTHROPIC_API_KEY) est lue depuis les variables d'environnement
// Cloudflare (jamais exposée côté client). Cette fonction reçoit les 10 derniers
// tirages (+ leurs éléments de classification) et renvoie un texte d'analyse.
//
// Déployée automatiquement par Cloudflare Pages car elle se trouve dans functions/api/.
// URL appelée depuis l'app : POST /api/analyse-ia

export async function onRequestPost(context) {
  try {
    const { request, env } = context;

    if (!env.ANTHROPIC_API_KEY) {
      return json({ error: "Clé API non configurée côté serveur (ANTHROPIC_API_KEY manquante)." }, 500);
    }

    const body = await request.json().catch(() => null);
    if (!body || !Array.isArray(body.tirages) || !body.tirages.length) {
      return json({ error: "Requête invalide : 'tirages' manquant ou vide." }, 400);
    }

    const { gameName, tirages } = body;

    // Construit un résumé texte lisible des tirages + éléments pour le prompt
    const lignes = tirages.map(t => {
      const nums = (t.n || []).join('-');
      const machine = t.m && t.m.length ? ` | Machine: ${t.m.join('-')}` : '';
      const elems = t.elements && t.elements.length ? ` | Éléments: ${t.elements.join(', ')}` : '';
      return `Tirage N°${t.tirage} (${t.date}) : ${nums}${machine}${elems}`;
    }).join('\n');

    const prompt = `Tu es un analyste de données pour un jeu de loto (à but purement récréatif/statistique — précise toujours qu'un loto reste un jeu de hasard et qu'aucune analyse ne peut prédire un tirage futur).

Voici les 10 derniers tirages du jeu "${gameName}", avec pour chaque numéro les éléments de sa classification (Counter, Bonanza, Malta, Key, Turning, Partner, Shadow, Code, Equiv, Miroir) quand ils s'appliquent :

${lignes}

Fais une analyse courte et claire (10-15 lignes maximum) de ces 10 tirages : numéros qui reviennent souvent, tendance des sommes, éléments de classification les plus représentés, et toute régularité notable. Termine par un rappel bref que ceci est purement statistique et ne garantit rien pour les prochains tirages. Réponds en français, dans un ton simple et direct, sans markdown (pas de titres ni de listes à puces, juste des paragraphes).`;

    const resp = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-api-key": env.ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
      },
      body: JSON.stringify({
        model: "claude-sonnet-4-5-20250929",
        max_tokens: 700,
        messages: [{ role: "user", content: prompt }],
      }),
    });

    if (!resp.ok) {
      const errText = await resp.text().catch(() => "");
      return json({ error: `Erreur API Claude (${resp.status})`, detail: errText.slice(0, 500) }, 502);
    }

    const data = await resp.json();
    const text = (data.content && data.content[0] && data.content[0].text) || "Réponse vide.";
    return json({ analyse: text });
  } catch (e) {
    return json({ error: "Erreur serveur", detail: String(e && e.message || e) }, 500);
  }
}

export async function onRequestOptions() {
  return new Response(null, { headers: corsHeaders() });
}

function corsHeaders() {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "content-type",
  };
}

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "content-type": "application/json", ...corsHeaders() },
  });
}
