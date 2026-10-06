"use strict";
// Receives the Play/Pause media key from content.js (via Firefox's Media Session) and applies
// it to all tabs: if any audible media is playing anywhere, pause all of it; otherwise resume
// only the media that was last started by hand.

const frames = new Map(); // "tabId:frameId" -> { port, media: Map<id, {playing, audible}> }
let history = [];         // [{ key, id, manual }], most recent last

const HISTORY_MAX = 50;

function remember(key, id, manual) {
  history = history.filter((h) => !(h.key === key && h.id === id));
  history.push({ key, id, manual });
  if (history.length > HISTORY_MAX) history.shift();
}

browser.runtime.onConnect.addListener((port) => {
  if (port.name !== "media" || !port.sender.tab) return;
  const key = `${port.sender.tab.id}:${port.sender.frameId}`;
  const frame = { port, media: new Map() };
  frames.set(key, frame);

  port.onMessage.addListener((msg) => {
    if (msg.type === "missing") {
      frame.media.delete(msg.id);
      history = history.filter((h) => !(h.key === key && h.id === msg.id));
      if (pendingResume) resume();
      return;
    }
    const was = frame.media.get(msg.id);
    frame.media.set(msg.id, { playing: msg.playing, audible: msg.audible });
    if (msg.type === "play") {
      pendingResume = false;
      if (msg.audible) remember(key, msg.id, msg.manual);
    } else if (msg.playing && msg.audible && msg.active && was && !was.audible) {
      // Was muted (e.g. muted autoplay) and has just been unmuted by a click or key press:
      // that counts as hand-started, and makes it the newest.
      remember(key, msg.id, true);
    } else if (msg.playing && msg.audible && !history.some((h) => h.key === key && h.id === msg.id)) {
      // Already playing when we first saw it (e.g. the extension was just installed):
      // keep it as a resume candidate, but not as a hand-started one.
      remember(key, msg.id, false);
    }
  });

  port.onDisconnect.addListener(() => {
    if (frames.get(key) === frame) frames.delete(key);
    history = history.filter((h) => h.key !== key || frames.has(key));
  });
});

function anyPlaying() {
  for (const f of frames.values()) {
    for (const m of f.media.values()) if (m.playing && m.audible) return true;
  }
  return false;
}

// Resume the newest hand-started media that still exists; if none, the newest of any kind.
// Media that is still playing (muted, so pauseAll left it alone) is not a candidate: play()
// on it does nothing. A frame answers "missing" when its element is gone, and resume() is
// retried.
let pendingResume = false;
function resume() {
  const live = history.filter((h) => {
    const m = frames.get(h.key)?.media.get(h.id);
    return m && !m.playing;
  });
  const target = live.findLast((h) => h.manual) ?? live.at(-1);
  pendingResume = Boolean(target);
  if (!target) return "nothing";
  frames.get(target.key).port.postMessage({ cmd: "play", id: target.id });
  return "resume";
}

function pauseAll() {
  let any = false;
  for (const f of frames.values()) {
    if ([...f.media.values()].some((m) => m.playing && m.audible)) {
      f.port.postMessage({ cmd: "pause" });
      any = true;
    }
  }
  if (any) pendingResume = false;
  return any ? "pause" : "nothing";
}

const toggle = () => (anyPlaying() ? pauseAll() : resume());

// Firefox turns Play/Pause into "play" or "pause" from the state of one tab, which can
// disagree with the other tabs, so "play" means toggle. An explicit Pause or Stop (a phone
// call via KDE Connect, headphones unplugged) only ever pauses.
browser.runtime.onMessage.addListener((msg) => {
  if (msg.type === "key") return Promise.resolve(msg.action === "play" ? toggle() : pauseAll());
});
