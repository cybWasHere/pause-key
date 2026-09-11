"use strict";
// Runs in every frame. Tracks this frame's media elements, reports their state to
// background.js over a port, and pauses/plays them when background.js asks. Frames with
// media also take over the Media Session play/pause/stop handlers, which is how Firefox
// delivers the keyboard's Play/Pause media key.

const byId = new Map();      // id -> WeakRef(element)
const ids = new WeakMap();   // element -> id
let nextId = 1;
let port = null;
let resuming = null;         // element we are playing on the Pause key's behalf
let lastHere = null;         // WeakRef to this frame's most recently started element
let claimed = false;         // our Media Session handlers are installed in this frame
const KEY_ACTIONS = ["play", "pause", "stop"];

const audible = (el) => !el.muted && el.volume > 0;
const playing = (el) => !el.paused && !el.ended;

function connect() {
  if (port) return port;
  port = browser.runtime.connect({ name: "media" });
  port.onMessage.addListener(onCommand);
  port.onDisconnect.addListener(() => { port = null; });
  return port;
}

function send(msg) {
  try {
    connect().postMessage(msg);
  } catch (e) {
    port = null; // extension reloaded or page frozen; next event reconnects
  }
}

function idOf(el) {
  let id = ids.get(el);
  if (!id) {
    id = nextId++;
    ids.set(el, id);
    byId.set(id, new WeakRef(el));
    claimMediaKeys();
    // Direct listeners catch elements that never enter the DOM (new Audio()).
    for (const t of ["play", "pause", "ended", "volumechange", "emptied"]) {
      el.addEventListener(t, onMediaEvent);
    }
  }
  return id;
}

function report(el, type) {
  const msg = { type, id: idOf(el), playing: playing(el), audible: audible(el) };
  if (type === "play") {
    lastHere = new WeakRef(el);
    // "Manual" = started by a click or key press on the page, not by us.
    msg.manual = el !== resuming && navigator.userActivation.isActive;
    if (el === resuming) resuming = null;
  }
  send(msg);
}

const seen = new WeakSet();  // an event can reach both the capture and element listener
function onMediaEvent(e) {
  const el = e.target;
  if (!(el instanceof HTMLMediaElement) || seen.has(e)) return;
  seen.add(e);
  report(el, e.type === "play" ? "play" : "state");
}

for (const t of ["play", "pause", "ended", "volumechange", "emptied"]) {
  window.addEventListener(t, onMediaEvent, true);
}

// Page scripts often play detached elements (new Audio()); hook play() to learn about them.
try {
  const proto = window.wrappedJSObject.HTMLMediaElement.prototype;
  const origPlay = proto.play;
  exportFunction(function () {
    try { idOf(this); } catch (e) {}
    return origPlay.call(this);
  }, proto, { defineAs: "play" });
} catch (e) {}

// Pages re-register their own play/pause handlers (YouTube does, per video). Once this frame
// has claimed the media keys, swallow those so ours stay in place. The guard sits on the
// page's mediaSession object itself and chains to whatever was there before, because other
// extensions (Plasma Browser Integration) wrap that same property: whichever of us loads
// first, page calls still pass through here. Our own calls go through the content script's
// Xray view and are not affected by any page-side override.
try {
  const ms = window.wrappedJSObject.navigator.mediaSession;
  const prev = ms.setActionHandler;
  exportFunction(function (action, handler) {
    if (claimed && KEY_ACTIONS.includes(String(action))) return undefined;
    return prev.call(this, action, handler);
  }, ms, { defineAs: "setActionHandler" });
} catch (e) {}

function claimMediaKeys() {
  if (claimed) return;
  claimed = true;
  for (const action of KEY_ACTIONS) {
    try { navigator.mediaSession.setActionHandler(action, onMediaKey); } catch (e) {}
  }
}

function pauseHere() {
  for (const ref of byId.values()) {
    const el = ref.deref();
    if (el && playing(el) && audible(el)) el.pause();
  }
}

// Firefox hands the media key to the active tab's Media Session: play/pause decisions are
// made across all tabs by background.js. If it knows of nothing to act on, fall back to
// what Firefox would have done without us, in this frame only.
function onMediaKey(details) {
  const action = String(details?.action);
  browser.runtime.sendMessage({ type: "key", action }).then((result) => {
    if (result !== "nothing") return;
    if (action === "play") {
      const el = lastHere?.deref();
      if (el) { resuming = el; el.play().catch(() => { resuming = null; }); }
    } else {
      pauseHere();
    }
  }, () => {});
}

function onCommand(msg) {
  if (msg.cmd === "pause") {
    pauseHere();
  } else if (msg.cmd === "play") {
    const el = byId.get(msg.id)?.deref();
    if (!el) {
      send({ type: "missing", id: msg.id });
      return;
    }
    resuming = el;
    el.play().catch(() => {
      resuming = null;
      send({ type: "missing", id: msg.id });
    });
  }
}

// Injected into an already-open page (extension just installed): pick up what's playing.
if (document.readyState !== "loading") {
  for (const el of document.querySelectorAll("audio, video")) {
    if (playing(el)) report(el, "state");
  }
}

// Back from the back/forward cache: the old port is gone, so re-announce what's playing.
window.addEventListener("pageshow", (e) => {
  if (!e.persisted) return;
  port = null;
  for (const ref of byId.values()) {
    const el = ref.deref();
    if (el) report(el, "state");
  }
});
