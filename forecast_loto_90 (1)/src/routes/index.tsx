import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Forecast Loto 90 — Analyse et comparaison de tirages" },
      {
        name: "description",
        content:
          "Analysez et comparez les tirages de plusieurs lotos, année par année, avec alignement et statistiques.",
      },
      { property: "og:title", content: "Forecast Loto 90" },
      {
        property: "og:description",
        content:
          "Comparez plusieurs lotos côte à côte, chacun sur l'année de votre choix.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

function Index() {
  return (
    <iframe
      src="/loto/index.html"
      title="Forecast Loto 90"
      className="h-screen w-screen border-0"
    />
  );
}
