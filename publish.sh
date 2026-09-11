#!/bin/sh
# Publish a public (listed) version on addons.mozilla.org: submits the version with the
# listing texts from amo-metadata.json (name, summary, description in English and French,
# categories, license, address addon/pause-key), then uploads the listing icon and
# screenshot if the listing has none yet.
# Mozilla reviews it before it goes public; AMO emails the result. Bump "version" in
# extension/manifest.json first: AMO refuses a version number it has seen before.
#
# Needs AMO API credentials: https://addons.mozilla.org/developers/addon/api/key/
set -eu
cd "$(dirname "$0")"

if [ -z "${WEB_EXT_API_KEY:-}" ]; then
    printf 'AMO JWT issuer (user:...): '; read -r WEB_EXT_API_KEY
fi
if [ -z "${WEB_EXT_API_SECRET:-}" ]; then
    printf 'AMO JWT secret (hidden): '; stty -echo; read -r WEB_EXT_API_SECRET; stty echo; echo
fi
# The issuer is "user:<id>:<n>"; AMO rejects it without the prefix.
case "$WEB_EXT_API_KEY" in user:*) ;; *) WEB_EXT_API_KEY="user:$WEB_EXT_API_KEY" ;; esac
export WEB_EXT_API_KEY WEB_EXT_API_SECRET

npx --yes web-ext@latest sign --channel=listed --amo-metadata amo-metadata.json \
    --source-dir extension --artifacts-dir dist --approval-timeout 0

# Icon and screenshot go on the listing after the version exists. Not fatal: they can also be
# added by hand in the Developer Hub (Edit Product Page -> Images).
python3 amo_assets.py || echo "Icon/screenshot upload failed: add art/icon-128.png and art/screenshot-en.png in the Developer Hub."

echo
echo "Submitted for review. Your listing: https://addons.mozilla.org/firefox/addon/pause-key/"
echo "(the page appears once Mozilla approves it; AMO emails you either way)"
