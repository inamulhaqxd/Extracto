<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

# Project conventions

## Hooks

- Never write `useState`/`useEffect`/`useCallback`/`useMemo`/`useReducer` inline inside a component in `src/components/` or `src/app/` (except generated shadcn primitives under `src/components/ui/`, which are exempt). Extract the logic into a dedicated hook under `src/hooks/`.
- A component should only *compose* hooks (call them, wire their return values together), never declare raw state itself.
- If a feature has a single hook, it lives flat: `src/hooks/use-thing.ts`.
- If a feature has multiple hooks, they live in their own subdirectory: `src/hooks/feature-name/use-thing.ts`.
- Use `.ts` for hooks with no JSX in them (the common case). Use `.tsx` only if the hook itself contains JSX syntax.
