# Frontend architecture

The Vite entry point is `frontend/src/main.tsx`. `app/App.tsx` composes the router and route-level shells. Reusable UI primitives live in `components/ui.tsx`, and design tokens plus responsive behavior live in `styles/tokens.css`.

`games/registry.ts` is the future activity boundary. Each definition includes domain, age range, difficulty, duration, and accessibility options. `gaze/types.ts` keeps camera providers out of game components. `services/apiClient.ts` is the only request helper in Stage 1.

The child shell uses simple language and large targets. Parent routes use explicit empty states rather than fake assessment results.
