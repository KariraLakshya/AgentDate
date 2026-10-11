// Copies the real demo bundle (produced by the round-robin job) into public/ if present.
// On Vercel (root dir = frontend) ../data does not exist, so the committed fixture is used.
import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const src = resolve(here, "../../data/demo/demo.json");
const dst = resolve(here, "../public/demo/demo.json");
mkdirSync(dirname(dst), { recursive: true });
if (existsSync(src)) {
  copyFileSync(src, dst);
  console.log("[copy-demo] copied", src);
} else if (existsSync(dst)) {
  console.log("[copy-demo] no ../data/demo/demo.json; keeping committed fixture");
} else {
  console.error("[copy-demo] no demo.json anywhere");
  process.exit(1);
}
