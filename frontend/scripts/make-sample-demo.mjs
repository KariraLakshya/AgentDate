// Generates the small SYNTHETIC sample fixture at public/demo/demo.json (used when the real
// data/demo/demo.json is absent, e.g. on Vercel). Run: node scripts/make-sample-demo.mjs
import { writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const cl = (value, evidence, source, confidence) => ({ value, evidence, source, confidence });
const tr = (value, evidence, confidence) => ({ value, evidence, confidence });
const mk = (o) => ({
  summary: o.summary,
  needs: o.needs, hobbies: o.hobbies, interests: o.interests, values: o.values,
  communication_style: o.comm, humor: o.humor, energy: o.energy,
  lifestyle: o.lifestyle, wants_in_partner: o.wants,
  linkedin_persona: { summary: o.li, evidence: o.liEv },
  instagram_persona: { summary: o.ig, evidence: o.igEv },
  persona_gap: { score: o.gap, description: o.gapD },
  identity_match: { score: o.idm, reason: o.idr },
  source_status: o.status,
});
const people = [
  { id: "syn-maya", display_name: "Maya Okafor", profile: mk({
    summary: "Product designer who treats weekends as trail-running time and wants a partner who is curious and unhurried.",
    needs: [cl("Space for solo time", "Sunday mornings are for me and a long trail.", "instagram", 0.8), cl("Intellectual curiosity in a partner", "Always asking 'why' - my team's favourite annoyance.", "linkedin", 0.7)],
    hobbies: [cl("Trail running", "Ran the Ridge 30k at dawn.", "instagram", 0.9), cl("Ceramics", "Wheel class number six. Still wonky.", "instagram", 0.75)],
    interests: [cl("Accessible design", "Led our accessibility audit across 40 screens.", "linkedin", 0.85)],
    values: [cl("Craft over speed", "I would rather ship it right than ship it Friday.", "linkedin", 0.8)],
    comm: tr("Direct but warm, asks follow-up questions", "Thread of replies asking 'what made you pick that?'", 0.7),
    humor: tr("Dry, self-deprecating", "Caption: 'my pottery is a cry for help'", 0.65),
    energy: tr("Steady, morning-oriented", "5:40am run selfies", 0.7),
    lifestyle: [cl("Early riser, plans ahead", "Calendar-blocking enthusiast.", "linkedin", 0.6)],
    wants: [cl("Someone who can be quiet with her", "Best dates are two coffees and no agenda.", "instagram", 0.55)],
    li: "Polished, systems-minded design lead.", liEv: ["Led accessibility audit", "Design systems talk 2024"],
    ig: "Muddy shoes, wonky mugs, long silences on trails.", igEv: ["Ridge 30k at dawn", "Wheel class number six"],
    gap: 0.35, gapD: "LinkedIn shows rigour; Instagram shows a much looser, more playful side.",
    idm: 0.92, idr: "Same name, city and design bio on both.", status: { linkedin: "ok", instagram: "ok" } }) },
  { id: "syn-theo", display_name: "Theo Lindqvist", profile: mk({
    summary: "Backend engineer and amateur chef who loves hosting dinners and long debates about food systems.",
    needs: [cl("Shared meals as a ritual", "Sunday supper for eight, every week.", "instagram", 0.8)],
    hobbies: [cl("Cooking for groups", "Braised short rib for eight. Nobody left hungry.", "instagram", 0.9), cl("Cycling", "Century ride done.", "instagram", 0.6)],
    interests: [cl("Distributed systems", "Wrote our consensus library.", "linkedin", 0.85), cl("Food systems", "Reading list: Salt Fat Acid Heat.", "instagram", 0.6)],
    values: [cl("Generosity", "Mentoring two juniors, always room at the table.", "linkedin", 0.7)],
    comm: tr("Storyteller, enthusiastic", "Long captions with a punchline.", 0.7),
    humor: tr("Punny", "Caption: 'a roux awakening'", 0.7),
    energy: tr("High, social", "Hosting photos weekly.", 0.75),
    lifestyle: [cl("Social, homebody", "Home is the venue.", "instagram", 0.6)],
    wants: [cl("A partner who enjoys a full table", "Looking for someone to share the dishes (and wash them).", "instagram", 0.5)],
    li: "Reliable, quietly senior engineer.", liEv: ["Consensus library", "Mentoring juniors"],
    ig: "Loud, warm host with a flour-dusted apron.", igEv: ["Sunday supper for eight", "A roux awakening"],
    gap: 0.5, gapD: "Professional reserve vs a boisterous, performative host online.",
    idm: 0.88, idr: "Name and city match; bio mentions engineering.", status: { linkedin: "ok", instagram: "ok" } }) },
  { id: "syn-priya", display_name: "Priya Raman", profile: mk({
    summary: "Climate analyst with a taste for board games and train travel; wants a partner who is kind and a little competitive.",
    needs: [cl("Playful competition", "House rules for Catan are non-negotiable.", "instagram", 0.7)],
    hobbies: [cl("Board games", "Game night host since 2021.", "instagram", 0.85), cl("Train travel", "Interrailing: 11 countries, 0 flights.", "instagram", 0.8)],
    interests: [cl("Climate policy", "Modelled grid decarbonisation scenarios.", "linkedin", 0.85)],
    values: [cl("Low-carbon living", "Chose trains over planes for 3 years.", "instagram", 0.75)],
    comm: tr("Precise, curious", "Careful explanations of methodology.", 0.6),
    humor: tr("Wry", "Caption: 'sorry, the model says no'", 0.55),
    energy: tr("Moderate, evenings", "Late-night game photos.", 0.5),
    lifestyle: [cl("Plans trips months ahead", "Spreadsheet for the Alps trip.", "instagram", 0.6)],
    wants: [cl("Someone patient with planning", "Planner seeks co-pilot.", "instagram", 0.4)],
    li: "Quantitative, careful analyst.", liEv: ["Grid decarbonisation model"],
    ig: "Playful gamer and slow traveller.", igEv: ["Interrailing 11 countries"],
    gap: 0.25, gapD: "Mostly consistent; Instagram is more playful.",
    idm: 0.7, idr: "Name matches; location differs slightly.", status: { linkedin: "ok", instagram: "thin" } }) },
  { id: "syn-jonas", display_name: "Jonas Weber", profile: mk({
    summary: "Little public footprint; a consultant who appears to enjoy climbing. Most fields are low confidence.",
    needs: [cl("Unclear", "No stated needs in public posts.", "linkedin", 0.2)],
    hobbies: [cl("Climbing", "Gym check-in: 'send day'", "instagram", 0.45)],
    interests: [cl("Strategy consulting", "Role: Senior consultant.", "linkedin", 0.6)],
    values: [cl("Not enough evidence", "No value statements found.", "linkedin", 0.15)],
    comm: tr("Terse", "Short posts.", 0.3), humor: tr("Unknown", "No signal.", 0.1), energy: tr("Unknown", "No signal.", 0.15),
    lifestyle: [cl("Travels for work", "Client-site updates.", "linkedin", 0.4)],
    wants: [cl("Unknown", "Nothing public.", "instagram", 0.1)],
    li: "Terse, professional.", liEv: ["Senior consultant"], ig: "Private-ish; a few climbing posts.", igEv: ["Send day"],
    gap: 0.4, gapD: "Too little data on Instagram to judge reliably.",
    idm: 0.55, idr: "Common name; only weak location overlap.", status: { linkedin: "ok", instagram: "not_readable" } }) },
].map((p) => ({ ...p, synthetic: true }));

const ids = people.map((p) => p.id);
const D = ["interest_overlap", "values_alignment", "communication_chemistry", "lifestyle_fit", "growth_potential"];
const rub = (b, verdict, again) => {
  const r = {};
  D.forEach((d, i) => (r[d] = Math.max(0, Math.min(10, b + ((i * 7 + b * 3) % 3) - 1))));
  r.would_meet_again = again;
  r.verdict = verdict;
  return r;
};
const base = {
  "syn-maya": { "syn-theo": 6, "syn-priya": 7, "syn-jonas": 4 },
  "syn-theo": { "syn-maya": 7, "syn-priya": 6, "syn-jonas": 4 },
  "syn-priya": { "syn-maya": 8, "syn-theo": 5, "syn-jonas": 5 },
  "syn-jonas": { "syn-maya": 6, "syn-theo": 5, "syn-priya": 6 },
};
const stages = ["opening", "opening", "shared_interests", "shared_interests", "friction", "values", "what_do_you_want", "close"];
const lines = [
  "Hi! I hear you spend a lot of time outdoors, or at least thinking about it.",
  "Guilty. Mornings are my favourite, mostly because nobody else is awake. What fills your weekends?",
  "A bit of everything honestly - things I can do with my hands. Do you plan them or let them happen?",
  "Plan, always. But I have been trying to leave an hour empty on purpose.",
  "Here is a spicy one: would you cancel a plan for something spontaneous?",
  "Depends who it is with. I do value showing up, though - reliability matters to me.",
  "What are you hoping to find, honestly?",
  "Someone curious, with room for quiet. I would happily do this again.",
];
const chem = [5, 5.5, 6, 6.5, 5, 6.5, 7.5, 8];
const dates = [];
const best = {};
for (let i = 0; i < ids.length; i++) for (let j = i + 1; j < ids.length; j++) {
  const a = ids[i], b = ids[j];
  const turns = lines.map((t, k) => {
    const spk = k % 2 === 0 ? a : b;
    const flags = [];
    if (k === 2) flags.push({ type: "spark", note: "Shared love of hands-on making" });
    if (k === 4) flags.push({ type: "friction", note: "Spontaneity vs planning" });
    if (k === 5) flags.push({ type: "repair", note: "Acknowledged the difference gracefully" });
    if (k === 3 && (a === "syn-theo" || b === "syn-theo")) flags.push({ type: "unsupported_claim", note: "Claims an 'empty hour' habit the profile does not mention" });
    const c = chem[k] + (((i + j) % 3) - 1) * 0.5;
    return { idx: k, speaker: spk, stage: stages[k], public_text: t,
      private_note: `Plan: probe ${k < 4 ? "interests" : "values"}. Chemistry ${c.toFixed(1)}/10. ${k === 4 ? "Friction noted; stay warm." : "Going well."}`,
      chemistry: Math.max(0, Math.min(10, c)), flags };
  });
  const flagged = turns.filter((t) => t.flags.some((f) => f.type === "unsupported_claim")).map((t) => t.idx);
  dates.push({ id: `${a}-${b}`, person_a: a, person_b: b, kind: "standard", status: "done", turns,
    score_a: rub(base[a][b], "Easy to talk to; would plan a second coffee.", base[a][b] >= 5),
    score_b: rub(base[b][a], "Thoughtful, a little guarded.", base[b][a] >= 5),
    faithfulness_a: 0.95, faithfulness_b: flagged.length ? 0.78 : 0.96, flagged_turns: flagged });
  best[`${a}|${b}`] = lines[2];
  best[`${b}|${a}`] = lines[7];
}
const wmean = (r) => D.reduce((s, d) => s + r[d], 0) / D.length;
const matrix = ids.map((a) => ids.map((b) => {
  if (a === b) return null;
  const d = dates.find((x) => (x.person_a === a && x.person_b === b) || (x.person_a === b && x.person_b === a));
  return Math.round(wmean(d.person_a === a ? d.score_a : d.score_b) * 100) / 100;
}));
const briefings = {};
for (const a of ids) {
  const row = matrix[ids.indexOf(a)];
  const others = ids.filter((x) => x !== a).sort((x, y) => row[ids.indexOf(y)] - row[ids.indexOf(x)]);
  briefings[a] = {
    introduce: [{ person_id: others[0], reason: "Strongest mutual chemistry and aligned values." }],
    warn: [{ person_id: others[others.length - 1], reason: "Low overlap in lifestyle; conversation stayed surface-level." }],
    unsure: ["Whether the low-confidence fields reflect the real person.", "How much weight to give the Instagram persona."],
  };
}
const out = resolve(dirname(fileURLToPath(import.meta.url)), "../public/demo/demo.json");
writeFileSync(out, JSON.stringify({ people, dates, matrix, order: ids, stable_pairs: [["syn-maya", "syn-priya"], ["syn-theo", "syn-jonas"]], briefings, best_moments: best }, null, 1));
console.log("wrote", out);
