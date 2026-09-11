#!/bin/sh
# Sign the extension on addons.mozilla.org as unlisted (private: not published, not
# searchable) and open the signed .xpi in Firefox to install it. Release Firefox only
# installs signed extensions permanently.
#
# Needs AMO API credentials: https://addons.mozilla.org/developers/addon/api/key/
# ("JWT issuer" = API key, "JWT secret" = API secret). Prompts if not in the environment.
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

npx --yes web-ext@latest sign --channel=unlisted --source-dir extension --artifacts-dir dist

xpi=$(ls -t dist/*.xpi | head -1)
echo "Signed: $xpi"
firefox "$xpi"
