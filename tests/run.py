#!/usr/bin/env python3
"""End-to-end tests for Pause Key in a throwaway headless Firefox.

    python3 tests/run.py [path/to/extension]

Media keys are injected with MediaControlService.generateMediaControlKey, the same pipeline
the OS media keys feed (MPRIS on Linux). Pages play a -60 dBFS tone (just above Firefox's
-72 dB audibility floor) routed to a temporary PipeWire/PulseAudio null sink, so nothing is
heard. Needs firefox, pactl and python3.
"""
import math, os, shutil, struct, subprocess, sys, tempfile, time, wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from marionette import Marionette

HERE = os.path.dirname(os.path.abspath(__file__))
EXT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "extension")
WWW = tempfile.mkdtemp(prefix="pausekey-www-")
PROFILE = tempfile.mkdtemp(prefix="pausekey-profile-")
for f in os.listdir(os.path.join(HERE, "www")):
    shutil.copy(os.path.join(HERE, "www", f), WWW)
with wave.open(os.path.join(WWW, "tone.wav"), "wb") as w:  # 10 s: Firefox ignores media under 3 s
    amp = int(32767 * 10 ** (-60 / 20))
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050)
    w.writeframes(b"".join(struct.pack("<h", int(amp * math.sin(2 * math.pi * 440 * i / 22050))) for i in range(22050 * 10)))
with open(os.path.join(PROFILE, "user.js"), "w") as f:
    f.write("""user_pref("marionette.port", 28291);
user_pref("media.mediacontrol.testingevents.enabled", true);
user_pref("browser.shell.checkDefaultBrowser", false);
user_pref("datareporting.policy.dataSubmissionEnabled", false);
user_pref("toolkit.telemetry.reportingpolicy.firstRun", false);
user_pref("browser.startup.homepage_override.mstone", "ignore");
user_pref("browser.aboutwelcome.enabled", false);
user_pref("app.update.disabledForTesting", true);
""")
L = "http://localhost:28391"
ELEM = "element-6066-11e4-a52e-4f735466cecf"

default_sink = subprocess.run(["pactl", "get-default-sink"], capture_output=True, text=True).stdout.strip()
mod = subprocess.run(["pactl", "load-module", "module-null-sink", "sink_name=pausekey_test",
                      "sink_properties=device.description=pausekey-test"], capture_output=True, text=True).stdout.strip()
http = subprocess.Popen([sys.executable, "-m", "http.server", "28391", "-d", WWW],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
ff = subprocess.Popen(["firefox", "--headless", "--no-remote", "-profile", PROFILE, "--marionette",
                       "-remote-allow-system-access"], env=dict(os.environ, MOZ_HEADLESS="1", PULSE_SINK="pausekey_test"),
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
fails = 0
try:
    m = Marionette(28291)
    m("WebDriver:NewSession", capabilities={})
    tabs = {}

    def open_tab(name, url):
        h = m("WebDriver:NewWindow", type="tab")["handle"] if tabs else m("WebDriver:GetWindowHandle")["value"]
        m("WebDriver:SwitchToWindow", handle=h); m("WebDriver:Navigate", url=url); tabs[name] = h

    def go(name):
        m("WebDriver:SwitchToWindow", handle=tabs[name])

    def frame_in():
        m("WebDriver:SwitchToFrame", element=m("WebDriver:FindElement", using="css selector", value="#f")["value"][ELEM])

    def click(name, frame=False):
        go(name)
        if frame: frame_in()
        m("WebDriver:ElementClick", id=m("WebDriver:FindElement", using="css selector", value="#play")["value"][ELEM])
        if frame: m("WebDriver:SwitchToParentFrame")
        time.sleep(0.8)

    def js(s):
        return m("WebDriver:ExecuteScript", script=s, args=[])["value"]

    def state(name):
        go(name)
        if name == "D":
            return js("return document.body.dataset.s || 'none'")
        if name == "F": frame_in()
        v = js("return document.getElementById('m').paused ? 'paused' : 'playing'")
        if name == "F": m("WebDriver:SwitchToParentFrame")
        return v

    def key(k="playpause"):
        m("Marionette:SetContext", value="chrome")
        m("WebDriver:ExecuteScript", script="MediaControlService.generateMediaControlKey(arguments[0])", args=[k])
        fx = m("WebDriver:ExecuteScript", script="return MediaControlService.getCurrentMediaSessionPlaybackState()", args=[])["value"]
        m("Marionette:SetContext", value="content")
        time.sleep(0.8)
        return f"{k} (firefox saw {fx})"

    def check(label, answer, want, extra=None):
        global fails
        got = {k: state(k) for k in want}
        ok = got == want and (extra is None or extra())
        fails += not ok
        print(f"{'PASS' if ok else 'FAIL'} {label}: key={answer} {got}")

    open_tab("P", f"{L}/page.html?pre"); time.sleep(1); click("P")
    print("addon:", m("Addon:Install", path=os.path.abspath(EXT), temporary=True))
    time.sleep(1.5)
    check("playing before install, media key -> paused", key(), {"P": "paused"})
    check("media key -> pre-install media resumes", key(), {"P": "playing"})
    check("media key -> paused again", key(), {"P": "paused"})

    open_tab("A", f"{L}/page.html?a"); open_tab("B", f"{L}/page.html?b")
    open_tab("M", f"{L}/muted.html"); open_tab("D", f"{L}/detached.html"); open_tab("F", f"{L}/frame.html")
    open_tab("Y", f"{L}/yt.html")
    time.sleep(1)

    click("A"); click("B")
    check("A,B by hand + muted autoplay; key -> pause all audible", key(), {"A": "paused", "B": "paused", "M": "playing"})
    check("key -> only last hand-played (B) resumes", key(), {"A": "paused", "B": "playing"})
    check("key -> B paused", key(), {"A": "paused", "B": "paused"})
    click("A")
    check("A by hand, key -> all paused", key(), {"A": "paused", "B": "paused"})
    check("key -> A resumes", key(), {"A": "playing", "B": "paused"})
    click("D")
    check("detached new Audio() by hand, key -> A and D paused", key(), {"A": "paused", "D": "paused"})
    check("key -> detached resumes", key(), {"D": "playing", "A": "paused"})
    click("F", frame=True)
    check("cross-origin iframe by hand, key -> F and D paused", key(), {"F": "paused", "D": "paused"})
    check("key -> iframe media resumes", key(), {"F": "playing", "D": "paused"})
    key()
    go("F"); m("WebDriver:CloseWindow"); del tabs["F"]; time.sleep(0.5)
    check("last hand-played tab closed, key -> previous (D) resumes", key(), {"D": "playing", "A": "paused", "B": "paused"})

    # A page with its own Media Session handlers (like YouTube) must not take the key back.
    click("Y")
    page_calls = lambda: (go("Y") or True) and js("return JSON.stringify(document.body.dataset)") in ("{}", '{"page_play":"0"}')
    check("YouTube-like page by hand + D playing, key -> both paused, page handlers not called",
          key(), {"Y": "paused", "D": "paused"}, page_calls)
    check("key -> YouTube-like resumes, page handlers not called", key(), {"Y": "playing", "D": "paused"}, page_calls)

    # Explicit keys: Pause/Stop only ever pause; Play toggles.
    check("explicit Stop -> all paused", key("stop"), {"Y": "paused", "D": "paused"})
    check("explicit Pause with nothing playing -> nothing starts", key("pause"), {"Y": "paused", "D": "paused", "A": "paused", "B": "paused"})
    check("explicit Play with nothing playing -> last hand-played (Y) resumes", key("play"), {"Y": "playing", "D": "paused"})
    click("A")
    check("A and Y playing, explicit Play (tab-state mismatch) -> pause all", key("play"), {"Y": "paused", "A": "paused"})
    # Plasma Browser Integration-style wrapper on top of the site's handlers.
    open_tab("K", f"{L}/pbi.html"); time.sleep(1); click("K")
    k_calls = lambda: (go("K") or True) and "page_" not in js("return JSON.stringify(document.body.dataset)")
    check("PBI-wrapped page + A playing, key -> both paused, page handlers not called", key(), {"K": "paused", "A": "paused"}, k_calls)
    check("key -> PBI-wrapped page resumes", key(), {"K": "playing", "A": "paused"}, k_calls)
    print("pbi-like dataset:", (go("K") or True) and js("return JSON.stringify(document.body.dataset)"))
    print("page handler calls on yt-like:", (go("Y") or True) and js("return JSON.stringify(document.body.dataset)"))
finally:
    try:
        m("Marionette:Quit")
    except Exception:
        pass
    time.sleep(2)
    ff.kill(); http.kill()
    if mod:
        subprocess.run(["pactl", "unload-module", mod])
    now = subprocess.run(["pactl", "get-default-sink"], capture_output=True, text=True).stdout.strip()
    print(f"default sink unchanged: {now == default_sink} ({now}); null sink module {mod} unloaded")
    shutil.rmtree(WWW, ignore_errors=True); shutil.rmtree(PROFILE, ignore_errors=True)
    print("FAILURES:", fails)
    sys.exit(1 if fails else 0)
