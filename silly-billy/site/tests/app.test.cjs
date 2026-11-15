const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

// Small DOM test double: executes the production script and its event handlers.
// No dependencies, network, database, or model required.
function setup(protocol = 'http:') {
  class Element {
    constructor() { this.children = []; this.listeners = {}; this.attributes = {}; this.hidden = false; this.disabled = false; this.textContent = ''; }
    append(...items) { this.children.push(...items); }
    replaceChildren() { this.children = []; }
    setAttribute(k, v) { this.attributes[k] = v; }
    addEventListener(k, fn) { this.listeners[k] = fn; }
    fire(k) { return this.listeners[k]?.({ preventDefault() {} }); }
  }
  const ids = Object.fromEntries(['upload-form', 'syllabus', 'status', 'summary', 'example', 'example-label', 'retry'].map(k => [k, new Element()]));
  const submit = new Element();
  ids['upload-form'].querySelector = () => submit;
  ids['upload-form'].requestSubmit = () => ids['upload-form'].fire('submit');
  ids.syllabus.files = [];
  const requests = [];
  let respond;
  const context = vm.createContext({
    document: { querySelector: s => ids[s.slice(1)], createElement: () => new Element() },
    location: { protocol },
    FormData: class { constructor() { this.entries = []; } append(...args) { this.entries.push(args); } },
    fetch: (...args) => { requests.push(args); return new Promise((resolve, reject) => { respond = { resolve, reject }; }); },
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../app.js'), 'utf8'), context);
  return { ids, submit, requests, select(name = 'course.pdf', size = 100) { ids.syllabus.files = [{ name, size }]; ids.syllabus.fire('change'); },
    send: () => ids['upload-form'].fire('submit'),
    resolve(data, ok = true) { respond.resolve({ ok, json: async () => data }); },
    nonJSON() { respond.resolve({ ok: false, json: async () => { throw Error(); } }); },
    reject() { respond.reject(Error('offline')); } };
}
const empty = () => ({ overview: [], due_dates: [], lecture_dates: [], exam_dates: [], grading: [] });

test('local validation rejects missing, wrong extension, empty and oversized files without requests', async () => {
  const h = setup();
  for (const selection of [null, ['notes.txt', 10], ['empty.pdf', 0], ['large.pdf', 25 * 1024 * 1024 + 1]]) {
    if (selection) h.select(...selection);
    await h.send();
    assert.equal(h.requests.length, 0);
    assert.equal(h.ids.summary.hidden, true);
    assert.equal(h.submit.disabled, false);
    assert.ok(h.ids.status.textContent.startsWith('Choose'));
  }
});

test('busy state blocks duplicates and example races, sends captured file, restores controls', async () => {
  const h = setup(); h.select(); h.ids.example.fire('click');
  assert.equal(h.ids['example-label'].hidden, false);
  const pending = h.send();
  assert.equal(h.ids.summary.children.length, 0);
  for (const control of [h.submit, h.ids.syllabus, h.ids.example, h.ids.retry]) assert.equal(control.disabled, true);
  assert.equal(h.ids['upload-form'].attributes['aria-busy'], 'true');
  await h.send(); h.ids.example.fire('click');
  assert.equal(h.requests.length, 1);
  assert.equal(h.ids.summary.hidden, true);
  assert.equal(h.requests[0][1].body.entries[0][1].name, 'course.pdf');
  h.resolve(empty()); await pending;
  assert.match(h.ids.status.textContent, /course.pdf/);
  assert.equal(h.ids.summary.children.length, 10);
  assert.equal(h.ids.summary.children[1].textContent, 'No details found in retrieved syllabus evidence');
  for (const control of [h.submit, h.ids.syllabus, h.ids.example, h.ids.retry]) assert.equal(control.disabled, false);
  assert.equal(h.ids['upload-form'].attributes['aria-busy'], 'false');
});

test('errors allow manual retry of same file with no automatic requests', async () => {
  for (const kind of ['network', 'nonJSON', 'malformed', 'api', 'unknown']) {
    const h = setup(); h.select(); const pending = h.send();
    if (kind === 'network') h.reject();
    if (kind === 'nonJSON') h.nonJSON();
    if (kind === 'malformed') h.resolve({ ...empty(), grading: ['uncited'] });
    if (kind === 'api') h.resolve({ error: 'Summary generation is unavailable. Please try again later.' }, false);
    if (kind === 'unknown') h.resolve({ error: '<secret>' }, false);
    await pending;
    assert.equal(h.ids.retry.hidden, false, kind);
    assert.equal(h.ids.summary.hidden, true);
    assert.equal(h.requests.length, 1);
    assert.equal(h.ids.syllabus.disabled, false);
    assert.doesNotMatch(h.ids.status.textContent, /secret/);
    const second = h.ids.retry.fire('click');
    assert.equal(h.requests.length, 2);
    h.resolve(empty()); await second;
    assert.equal(h.ids.retry.hidden, true);
    assert.equal(h.ids.summary.hidden, false);
    h.select('new.pdf');
    assert.equal(h.ids.summary.hidden, true);
    assert.match(h.ids.status.textContent, /new.pdf/);
  }
});

test('valid five-field response preserves facts and citations as text; malformed shapes fail', async () => {
  const h = setup(); h.select('limit.PDF', 25 * 1024 * 1024);
  let pending = h.send(); h.resolve({ ...empty(), overview: ['<img src=x> [Page 1] [Page 3]'] }); await pending;
  assert.equal(h.ids.summary.children[1].children[0].children[0].textContent, '<img src=x> [Page 1] [Page 3]');
  for (const data of [null, [], {}, { ...empty(), extra: [] }, { ...empty(), grading: [42] }, { ...empty(), overview: ['fact [Page 0]'] }]) {
    pending = h.send(); h.resolve(data); await pending;
    assert.equal(h.ids.summary.hidden, true);
    assert.match(h.ids.status.textContent, /invalid summary/);
  }
});

test('file demo works and never uploads; example is labeled', async () => {
  const h = setup('file:'); h.select(); await h.send();
  assert.equal(h.requests.length, 0);
  assert.match(h.ids.status.textContent, /Python server/);
  h.ids.example.fire('click');
  assert.equal(h.ids.summary.hidden, false);
  assert.equal(h.ids['example-label'].hidden, false);
  assert.match(h.ids.status.textContent, /Sample/);
});
