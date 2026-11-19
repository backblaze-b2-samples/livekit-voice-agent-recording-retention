/**
 * Public type surface of this workspace's shared package.
 *
 * Hand-written barrel, on purpose. Everything the API can describe is
 * GENERATED into `./generated/api-types.ts` by `pnpm gen:api` (from
 * `docs/api/openapi.json`, which `pnpm contract:export` writes from the
 * FastAPI routers and Pydantic models). Re-exporting it from here keeps the
 * import path stable for every consumer, so adding a backend model costs no
 * edits anywhere in the frontend.
 *
 * Add a type here only when the API knows nothing about it — a browser-side
 * concept with no wire representation. A type that *does* have a wire
 * representation belongs on the Pydantic model, where the contract, the
 * generated TypeScript and `/docs` all pick it up at once.
 */
export type * from "./generated/api-types";

