// Flip app/page.tsx from request-time rendering to build-time prerendering, for
// the GitHub Pages export.
//
// WHY A SCRIPT. Next requires `export const dynamic` to be a statically-parsable
// literal, so the value cannot be branched on an environment variable at all.
// The choice is between a hidden conditional Next rejects, two near-duplicate page
// files that will drift, and one explicit substitution. This is the third: it runs
// only in the Pages workflow, it asserts on the exact text it expects, and it fails
// loudly if the page changes shape rather than silently exporting a dynamic page.
//
//   node scripts/prepare-static-export.mjs          # force-dynamic -> force-static
//   node scripts/prepare-static-export.mjs --revert # and back

import { readFileSync, writeFileSync } from "node:fs";

const PAGE = "app/page.tsx";
const DYNAMIC = 'export const dynamic = "force-dynamic";';
const STATIC = 'export const dynamic = "force-static";';

const revert = process.argv.includes("--revert");
const [from, to] = revert ? [STATIC, DYNAMIC] : [DYNAMIC, STATIC];

const source = readFileSync(PAGE, "utf8");
if (source.includes(to) && !source.includes(from)) {
  console.log(`${PAGE} is already ${revert ? "dynamic" : "static"}; nothing to do`);
  process.exit(0);
}
if (!source.includes(from)) {
  console.error(
    `expected to find in ${PAGE}:\n  ${from}\nThe page changed shape — update this script.`,
  );
  process.exit(1);
}
writeFileSync(PAGE, source.replace(from, to), "utf8");
console.log(`${PAGE}: ${from.trim()} -> ${to.trim()}`);
