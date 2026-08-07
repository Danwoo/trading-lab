// Project-level ambient type declarations.
// Included via tsconfig `include: ["**/*.ts", ...]`.

// styled-jsx augments react's `StyleHTMLAttributes` with `jsx`/`global` props.
// Its type entry (`styled-jsx/index.d.ts`) references `./global`, which carries
// that augmentation. Loading it here makes `<style jsx>` / `<style jsx global>`
// type-check without touching the JSX call sites.
/// <reference types="styled-jsx" />

// CSS side-effect imports (`import "@/styles/globals.css"`) have no type by
// default. Declare the module so the import resolves as a side-effect.
declare module "*.css";
