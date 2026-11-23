const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { resolve } = require("node:path");
const { runInNewContext } = require("node:vm");
const file = resolve(process.env.VOCAB_JS || "assets/js/daily-extras.js");
const js = readFileSync(file, "utf8");
const day = "2026-11-23";
const sameDay = { date: day, words: [{ kanji: "試験" }] };
const wrongDay = { date: "2026-11-15", words: [{ kanji: "前日" }] };
const ok = (payload) => ({ ok: true, json: async () => payload });

function browser(answers, source = js) {
  const calls = [];
  const rendered = [];
  const desk = { dataset: {}, textContent: "", setAttribute() {} };
  const init = "  init();";
  assert.equal(source.split(init).length, 2);
  const modified = source.replace(init,
    "renderDailyVocab = (payload) => globalThis.rendered.push(payload.date); globalThis.load = loadDailyVocab;");
  const box = {
    rendered,
    URL,
    window: { addEventListener() {} },
    document: { querySelector: () => desk },
    console: { warn() {} },
    fetch: async (uri) => { calls.push(uri); return answers.shift(); },
  };
  runInNewContext(modified, box);
  return { calls, rendered, desk, load: box.load };
}

test("accepts dated vocabulary for the displayed edition", async () => {
  const t = browser([ok(sameDay)]);
  await t.load(day);
  assert.deepEqual(t.rendered, [day]);
  assert.deepEqual(t.calls, ["data/vocab/2026-11-23.json"]);
});

test("404 followed by stale latest keeps the correct unavailable state", async () => {
  const t = browser([{ ok: false, status: 404 }, ok(wrongDay)]);
  await t.load(day);
  assert.deepEqual(t.rendered, []);
  assert.match(t.desk.textContent, /2026-11-23.*暫未發布/);
  assert.deepEqual(t.calls, ["data/vocab/2026-11-23.json", "data/vocab/latest.json"]);
});

test("latest restores availability only for the same date", async () => {
  const t = browser([ok(wrongDay), ok(sameDay)]);
  await t.load(day);
  assert.deepEqual(t.rendered, [day]);
});

test("invalid edition values cannot reach the network", async () => {
  const t = browser([]);
  await t.load("../latest");
  assert.deepEqual(t.calls, []);
});
