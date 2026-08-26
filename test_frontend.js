/* Frontend logic tests — extracts the <script> from index.html and runs it in a
   VM sandbox with a DOM stub. Verifies i18n, state, phases, penalty, oath, rooms. */
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const html = fs.readFileSync(path.join(__dirname, "static", "index.html"), "utf8");
const m = html.match(/<script>([\s\S]*?)<\/script>/);
if (!m) { console.error("no <script> found"); process.exit(1); }
const code = m[1];

let passed = 0, failed = 0;
function check(name, cond) {
  if (cond) { passed++; console.log("  ✓ " + name); }
  else { failed++; console.log("  ✗ " + name); }
}

/* ---- DOM stub ---- */
function makeEl(id) {
  const listeners = {};
  const el = {
    id, value: "", textContent: "", innerHTML: "", disabled: false,
    style: {}, dataset: {}, title: "",
    classList: {
      _set: new Set(),
      add(c) { this._set.add(c); },
      remove(c) { this._set.delete(c); },
      toggle(c, force) { const has = this._set.has(c); const want = force === undefined ? !has : force; want ? this._set.add(c) : this._set.delete(c); return want; },
      contains(c) { return this._set.has(c); },
    },
    addEventListener(type, fn) { (listeners[type] = listeners[type] || []).push(fn); },
    appendChild() {},
    querySelectorAll() { return []; },
    closest() { return null; },
    click() { (listeners["click"] || []).forEach(fn => fn({ target: this })); },
    getContext() { return { clearRect(){}, save(){}, restore(){}, translate(){}, rotate(){}, fillRect(){}, set fillStyle(v){}, set globalAlpha(v){} }; },
    scrollTop: 0, scrollHeight: 0,
  };
  return el;
}
const els = {};
const documentStub = {
  getElementById(id) { if (!els[id]) els[id] = makeEl(id); return els[id]; },
  querySelector(sel) {
    // map #id and .class[data-for] selectors
    if (sel.startsWith("#")) { const id = sel.slice(1); if (!els[id]) els[id] = makeEl(id); return els[id]; }
    if (sel.includes("data-for")) { return makeEl("genderbtn"); }
    if (sel.startsWith(".")) { return makeEl("cls"); }
    return makeEl("q");
  },
  querySelectorAll() { return []; },
  createElement() { return makeEl("dyn"); },
  addEventListener() {}, removeEventListener() {},
  documentElement: { lang: "en", style: { setProperty(){} } },
  body: { classList: { _set: new Set(), add(){}, remove(){}, toggle(){}, contains(){ return false; } } },
};

const localStorageStub = { _d: {}, getItem(k){ return this._d[k] ?? null; }, setItem(k,v){ this._d[k]=String(v); }, removeItem(k){ delete this._d[k]; } };

const sandbox = {
  console,
  document: documentStub,
  localStorage: localStorageStub,
  fetch: async () => ({ ok: true, json: async () => ({}), blob: async () => new Blob() }),
  Audio: function(){ return { play: async()=>{}, pause(){} }; },
  URL: { createObjectURL: () => "blob:x" },
  navigator: { vibrate: () => {} },
  performance: { now: () => Date.now() },
  requestAnimationFrame: (fn) => 0,
  addEventListener: () => {},
  innerWidth: 400, innerHeight: 800,
  confirm: () => true,
  setTimeout: (fn) => 0, clearTimeout: () => {},
  setInterval: () => 0, clearInterval: () => {},
  Blob: function(){},
  AudioContext: function(){ return { currentTime: 0, createOscillator: ()=>({connect(){},start(){},stop(){},type:"",frequency:{value:0}}), createGain: ()=>({connect(){},gain:{setValueAtTime(){},exponentialRampToValueAtTime(){}}}), destination:{} }; },
  webkitAudioContext: function(){ return {}; },
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
sandbox.__netCalls = [];
vm.createContext(sandbox);

try {
  vm.runInContext(code, sandbox, { filename: "index.html" });
} catch (e) {
  console.error("SCRIPT ERROR:", e.message);
  process.exit(1);
}

const S = sandbox.window.state;

/* ---- 1. i18n ---- */
console.log("\n[i18n]");
const I18N = sandbox.window.I18N;
check("10 languages defined", ["en","es","fr","de","it","pt","hi","ja","zh","ar"].every(c => I18N[c]));
check("t() returns English by default", typeof sandbox.window.t("spin") === "string" && sandbox.window.t("spin").length > 0);
check("t() interpolates vars", sandbox.window.t("chooseFate", {name: "Alex"}).includes("Alex"));
check("t() falls back to English for missing key", sandbox.window.t("nonexistent_key_xyz") === "nonexistent_key_xyz");
check("Arabic is RTL", I18N.ar.rtl === true);
check("English is not RTL", I18N.en.rtl === false);
check("each lang has phases array", ["en","es","fr","de","it","pt","hi","ja","zh","ar"].every(c => Array.isArray(I18N[c].phases) && I18N[c].phases.length === 5));
check("each lang has heatNames", ["en","es","fr","de","it","pt","hi","ja","zh","ar"].every(c => Array.isArray(I18N[c].heatNames) && I18N[c].heatNames.length === 11));
check("each lang has banter", ["en","es","fr","de","it","pt","hi","ja","zh","ar"].every(c => Array.isArray(I18N[c].banter) && I18N[c].banter.length >= 3));

/* ---- 2. state ---- */
console.log("\n[state]");
check("state exists", !!S);
check("TRUTH_LIMIT = 3", sandbox.window.TRUTH_LIMIT === 3);
check("PENALTY = 100", sandbox.window.PENALTY === 100);
check("OATH_ROUND = 5", sandbox.window.OATH_ROUND === 5);
check("state has prefs", "prefs" in S);
check("state has mode", S.mode === "solo");
check("state has roomCode", "roomCode" in S);

/* ---- 3. phases (mystery) ---- */
console.log("\n[phases]");
check("phase r1 = First Glance", sandbox.phaseForRound(1).name === "First Glance");
check("phase r3 = Warming Up", sandbox.phaseForRound(3).name === "Warming Up");
check("phase r5 = The Oath", sandbox.phaseForRound(5).name === "The Oath");
check("phase r6 = Unveiling", sandbox.phaseForRound(6).name === "Unveiling");
check("phase r10 = No Secrets Left", sandbox.phaseForRound(10).name === "No Secrets Left");
S.round = 1; sandbox.renderPhase();
check("renderPhase sets pill", els["phasePill"].innerHTML.includes("First Glance"));
S.round = 10; sandbox.renderPhase();
check("renderPhase updates pill", els["phasePill"].innerHTML.includes("No Secrets Left"));

/* ---- 4. penalty ledger ---- */
console.log("\n[penalty]");
S.ledger = {};
S.players = [{ name: "Alex", gender: "male" }, { name: "Sam", gender: "female" }];
sandbox.window.renderLedger();
check("ledger starts at $0", els["ledger"].innerHTML.includes("$0"));
sandbox.window.recordPenalty("Alex", "skipped a dare step");
check("recordPenalty adds $100", sandbox.window.penaltyTotal("Alex") === 100);
check("ledger shows $100", els["ledger"].innerHTML.includes("$100"));
sandbox.window.recordPenalty("Alex", "refused a truth");
check("second penalty = $200", sandbox.window.penaltyTotal("Alex") === 200);
check("other player still $0", sandbox.window.penaltyTotal("Sam") === 0);

/* ---- 5. oath ---- */
console.log("\n[oath]");
S.oathSworn = false;
S.round = 5;
sandbox.window.showOath();
check("showOath reveals card", !els["oathCard"].classList.contains("hidden"));
check("oath text mentions $100", els["oathText"].innerHTML.includes("$100"));
check("oath text mentions seriously", els["oathText"].innerHTML.toLowerCase().includes("seriously"));
check("spin disabled during oath", els["spinBtn"].disabled === true);
els["oathBtn"].click();
check("oath sworn sets flag", S.oathSworn === true);
check("oath card hidden after swear", els["oathCard"].classList.contains("hidden"));
check("spin re-enabled after oath", els["spinBtn"].disabled === false);

/* ---- 6. streaks ---- */
console.log("\n[streaks]");
S.truthStreak = { Alex: 0, Sam: 0 };
sandbox.window.renderStreaks();
check("streak renders", els["streaks"].innerHTML.includes("Alex"));
S.truthStreak.Alex = 2;
sandbox.window.renderStreaks();
check("forced streak shows DARE", els["streaks"].innerHTML.includes("DARE"));

/* ---- 7. persistence ---- */
console.log("\n[persistence]");
S.heat = 6; S.round = 7; S.oathSworn = true; S.ledger = { Alex: [{ reason: "x", amount: 100 }] };
S.prefs = { Alex: { turnons: "feathers", fantasy: "", boundary: "no" } };
sandbox.window.saveState();
const saved = JSON.parse(localStorageStub.getItem("dirtytruth_save_v1"));
check("saveState persists oathSworn", saved.oathSworn === true);
check("saveState persists ledger", saved.ledger.Alex.length === 1);
check("saveState persists prefs", saved.prefs.Alex.turnons === "feathers");
check("saveState persists mode", saved.mode === "solo");
const loaded = sandbox.window.loadState();
check("loadState restores", loaded === true);
check("loadState restores heat", S.heat === 6);
check("loadState restores prefs", S.prefs.Alex.turnons === "feathers");

/* ---- 8. esc ---- */
check("esc escapes html", sandbox.window.esc('<b>"x"</b>') === "&lt;b&gt;&quot;x&quot;&lt;/b&gt;");

/* ---- 9. i18n switching ---- */
console.log("\n[i18n switch]");
sandbox.window.setUiLang("es");
check("Spanish spin", sandbox.window.t("spin").includes("botella"));
sandbox.window.setUiLang("ja");
check("Japanese spin", sandbox.window.t("spin").includes("ボトル"));
sandbox.window.setUiLang("ar");
check("Arabic spin", sandbox.window.t("spin").includes("القارورة"));
sandbox.window.setUiLang("en");

/* ---- 10. v5.1 i18n parity (new keys in every language) ---- */
console.log("\n[v5.1 i18n parity]");
const NEW_KEYS = ["roomWatching","roomGone","resynced","spinSpinning","craftTruth","craftDare","netFail","skipConfirm","refuseConfirm"];
const LANGS = ["en","es","fr","de","it","pt","hi","ja","zh","ar"];
check("all langs have new v5.1 keys", LANGS.every(l => NEW_KEYS.every(k =>
  typeof I18N[l][k] === "string" && I18N[l][k].length > 0)));
check("no raw ${p} placeholder leaked into strings", LANGS.every(l =>
  !I18N[l].skipConfirm.includes("${") && !I18N[l].refuseConfirm.includes("${")));
check("skipConfirm interpolates name+p($100)", sandbox.window.t("skipConfirm", {name:"Alex", p:"$100"}).includes("$100"));
check("refuseConfirm interpolates type word",
  sandbox.window.t("refuseConfirm", {name:"Alex", p:"$100", type:sandbox.window.t("dare")}).includes(sandbox.window.t("dare")));
check("roomWatching interpolates code", sandbox.window.t("roomWatching", {code:"KISS"}).includes("KISS"));

/* ---- 11. timer math (drift-proof) ---- */
console.log("\n[timer math]");
const cr = sandbox.window.computeRemaining;
check("computeRemaining exists", typeof cr === "function");
check("future deadline counts down", Math.abs(cr(Date.now() + 2000, Date.now()) - 2) < 0.001);
check("past deadline clamps to zero", cr(Date.now() - 5000, Date.now()) === 0);
check("one hour ahead = 3600s", Math.abs(cr(Date.now() + 3600000, Date.now()) - 3600) < 0.001);

/* ---- 12. wake lock guards ---- */
console.log("\n[wake lock]");
check("requestWakeLock defined and safe without API", typeof sandbox.requestWakeLock === "function");
check("releaseWakeLock defined", typeof sandbox.releaseWakeLock === "function");

/* ---- 13. persistence keeps room session across reload ---- */
console.log("\n[room session persistence]");
S.roomCode = "KISS"; S.role = "guest"; S.mode = "room";
sandbox.window.saveState();
const saved2 = JSON.parse(localStorageStub.getItem("dirtytruth_save_v1"));
check("saveState persists roomCode", saved2.roomCode === "KISS");
check("saveState persists role", saved2.role === "guest");
const loaded2 = sandbox.window.loadState();
check("loadState restores roomCode", S.roomCode === "KISS" && loaded2 === true);
check("loadState restores role", S.role === "guest");

/* ---- 14. PWA manifest + icon shipped ---- */
console.log("\n[pwa]");
const manRaw = fs.readFileSync(path.join(__dirname, "static", "manifest.webmanifest"), "utf8");
const man = JSON.parse(manRaw);
check("manifest has start_url /", man.start_url === "/");
check("manifest references icon.svg", Array.isArray(man.icons) && man.icons.some(i => String(i.src).endsWith("icon.svg")));
check("icon.svg exists and is svg", fs.readFileSync(path.join(__dirname, "static", "icon.svg"), "utf8").includes("<svg"));
check("index.html links manifest", html.includes('rel="manifest"'));

/* ---- 15. room mirror (v5.2): guests see challenges, steps, round ends ---- */
console.log("\n[room mirror]");
sandbox.fetch = async (url) => {
  sandbox.__netCalls.push(String(url));
  return { ok: true, json: async () => ({}), blob: async () => new Blob() };
};
S.role = "guest"; S.roomCode = "KISS";
S.players = [{ name: "H", gender: "male" }, { name: "G", gender: "female", joined: true }];
S.oathSworn = false;
const dareChal = { type: "dare", title: "The Slow Gaze", steps: [{ instruction: "Look.", seconds: 30 }, { instruction: "Breathe.", seconds: 20 }] };
function feedState(over) {
  return Object.assign({
    heat: 2, round: 1, target: { name: "G" }, challenge: dareChal, stepIdx: 0,
    status: "playing", players: S.players, truthStreak: {}, ledger: {},
    oathSworn: false, recent: [], prefs: {}, lang: "en",
  }, over);
}
sandbox.applyRemoteState(feedState({}));
check("mirror renders fresh challenge", els["qTitle"].textContent === "The Slow Gaze");
check("mirror signature tracked", sandbox.__MIRROR.renderedSig.length > 0);
check("mirrored dare badge set", els["qType"].textContent.includes("DARE"));
check("no state broadcast from a pure mirror", !sandbox.__netCalls.some(u => u.includes("/api/room/action")));

sandbox.applyRemoteState(feedState({ stepIdx: 1 }));
check("step advance mirrored into timer", !els["timerCard"].classList.contains("hidden"));
check("appliedStep advanced to 1", sandbox.__MIRROR.appliedStep === 1);

sandbox.applyRemoteState(feedState({ challenge: null, round: 2, heat: 3 }));
check("round end shows done card", !els["doneCard"].classList.contains("hidden"));
check("signature cleared after round", sandbox.__MIRROR.renderedSig === "");

/* host pulls guest-contributed fields while keeping game flow ownership */
S.role = "host";
sandbox.applyRemoteState(feedState({
  status: "setup", target: null, challenge: null,
  truthStreak: { G: 2 }, ledger: { G: [{ reason: "refused a dare", amount: 100 }] },
}));
check("host accepts guest penalty ledger", S.ledger.G && S.ledger.G.length === 1);
check("host accepts guest streak", S.truthStreak.G === 2);
check("streak pill re-rendered on host", els["streaks"].innerHTML.includes("G"));

/* oath arrives through the feed exactly once */
S.role = "guest"; S.oathSworn = false;
sandbox.applyRemoteState(feedState({ status: "oath", challenge: null, round: 5 }));
check("guest sees oath mirrored from feed", !els["oathCard"].classList.contains("hidden"));
const actionsAfterOath = sandbox.__netCalls.filter(u => u.includes("/api/room/action") && u.includes("set_status")).length;
check("guest mirror does not re-broadcast oath", actionsAfterOath === 0);

/* ---- 16. language dropdown fixes (v5.3) ---- */
console.log("\n[language dropdown]");
check("all langs have translated oath keys", LANGS.every(l =>
  typeof I18N[l].oathIntro === "string" && I18N[l].oathIntro.length > 0 &&
  typeof I18N[l].oathBody === "string" && I18N[l].oathBody.includes("{p}")));
check("en oath interpolates $100 penalty", sandbox.window.t("oathBody", {p:"$100"}).includes("$100"));
const langSel = sandbox.document.querySelector("#langSelect");
S.role = "host"; S.roomCode = "KISS"; S.oathSworn = true;
sandbox.__netCalls.length = 0;
sandbox.applyRemoteState({ lang: "es", heat: 2, round: 1, target: null, challenge: null,
  stepIdx: 0, status: "setup", players: S.players, truthStreak: {}, ledger: {},
  oathSworn: true, recent: [], prefs: {} });
check("partner device follows a remote language switch", sandbox.getUiLang() === "es");
check("dropdown mirrors the active language", langSel.value === "es");
check("following a switch sends no broadcast echo",
  !sandbox.__netCalls.some(u => u.includes("/api/room/action")));
check("switching language does not replay challenge TTS (silent re-render)",
  !sandbox.__netCalls.some(u => u.includes("/api/tts")));
sandbox.window.setUiLang("en"); langSel.value = "en";

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
