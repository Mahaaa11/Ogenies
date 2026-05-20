import type { NextConfig } from "next";

// Pour le mutualise PlanetHoster N0C, on deploie le front en export statique.
// Active "export" uniquement quand on construit pour la prod (NEXT_BUILD_TARGET=export).
// En dev local, on garde le mode classique (next dev).
const isStaticExport = process.env.NEXT_BUILD_TARGET === "export";

const nextConfig: NextConfig = {
  ...(isStaticExport
    ? {
        output: "export",
        // Sur mutualise sans optimiseur d'images server-side.
        images: { unoptimized: true },
        // Genere /route/index.html plutot que /route.html : ami avec Apache/Nginx
        // sans regles de reecriture.
        trailingSlash: true,
      }
    : {}),
};

export default nextConfig;
