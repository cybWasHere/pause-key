#!/usr/bin/env python3
"""Upload the listing icon and screenshot to addons.mozilla.org, once.

Used by publish.sh. Needs WEB_EXT_API_KEY / WEB_EXT_API_SECRET (AMO JWT issuer / secret).
Skips the icon if the listing already has a custom one, and the screenshot if any exist,
so running it again does not add duplicates.
"""
import base64, hashlib, hmac, json, os, sys, time, uuid, urllib.request, urllib.error

API = "https://addons.mozilla.org/api/v5/addons/addon/pause-key@cyb.rip/"
HERE = os.path.dirname(os.path.abspath(__file__))
ICON = os.path.join(HERE, "art", "icon-128.png")
SHOT = os.path.join(HERE, "art", "screenshot-en.png")
CAPTION = {"en-US": "One key, every tab: Play/Pause pauses everything, then resumes only what you started last.",
           "fr": "Une touche, tous les onglets : Lecture/Pause met tout en pause, puis ne relance que votre dernier média."}


def jwt():
    b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=")
    now = int(time.time())
    head = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = b64(json.dumps({"iss": os.environ["WEB_EXT_API_KEY"], "jti": str(uuid.uuid4()),
                           "iat": now, "exp": now + 60}).encode())
    sig = b64(hmac.new(os.environ["WEB_EXT_API_SECRET"].encode(), head + b"." + body, hashlib.sha256).digest())
    return (head + b"." + body + b"." + sig).decode()


def call(url, method="GET", data=None, content_type=None):
    req = urllib.request.Request(url, data=data, method=method, headers={"Authorization": "JWT " + jwt()})
    if content_type:
        req.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        sys.exit(f"AMO {method} {url} failed: {e.code} {e.read().decode()[:500]}")


def multipart(field, path):
    boundary = uuid.uuid4().hex
    data = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{field}\"; "
            f"filename=\"{os.path.basename(path)}\"\r\nContent-Type: image/png\r\n\r\n").encode()
    data += open(path, "rb").read() + f"\r\n--{boundary}--\r\n".encode()
    return data, f"multipart/form-data; boundary={boundary}"


addon = call(API)
if "default" in (addon.get("icon_url") or "default"):
    call(API, "PATCH", *multipart("icon", ICON))
    print("Uploaded listing icon.")
else:
    print("Listing icon already set, skipped.")

if not addon.get("previews"):
    preview = call(API + "previews/", "POST", *multipart("image", SHOT))
    call(f"{API}previews/{preview['id']}/", "PATCH", json.dumps({"caption": CAPTION}).encode(), "application/json")
    print("Uploaded screenshot.")
else:
    print(f"Listing already has {len(addon['previews'])} screenshot(s), skipped.")
