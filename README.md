<p align="center"><img src="art/icon-128.png" width="96" alt=""></p>

# Pause Key

A Firefox extension that makes your Play/Pause media key behave the way you'd expect with lots of tabs open:

- **Something is playing, in any tab:** Play/Pause pauses **all** of it.
- **Nothing is playing:** Play/Pause resumes **only the media you last started yourself**, not the autoplaying clip in another tab, and not everything at once.

It uses Firefox's own media-key support, so it works while Firefox is in the background, on Linux, Windows and macOS. There is nothing to install besides the extension.

## Install

From addons.mozilla.org: *link coming once the listing is approved*.

## Using a key other than a media key

Pause Key reacts to the standard media Play/Pause key. If your keyboard has none, map any key to it:

| System | How |
|---|---|
| KDE Plasma | System Settings → Shortcuts → *Media Controller* → *Play/Pause media playback* → set your key |
| GNOME | Settings → Keyboard → View and Customise Shortcuts → *Sound and Media* → *Play (or play/pause)* → set your key |
| Windows | [Microsoft PowerToys](https://learn.microsoft.com/windows/powertoys/keyboard-manager) → Keyboard Manager → remap your key to *Play/Pause Media* |
| macOS | Use the ▶︎❙❙ key (F8) |

### Things that can take the key before Firefox

Your system sends media keys to one player, usually the one used most recently. If another app (Spotify, VLC…) played after Firefox, the key goes there.

**KDE users with Plasma Browser Integration:** turn off its **Media Controls** option (Add-ons → Plasma Integration → Preferences). Otherwise Plasma may send the key to Plasma Integration's own player, which controls a single tab directly and bypasses Pause Key.

## How it decides

- "Playing" means audible: unmuted, volume above zero. Muted autoplay videos are ignored, so they can't swallow your key press.
- "Started by you" means playback began within a few seconds of a click or key press on that page. When nothing you started is known (right after installing, for instance), it resumes whatever played most recently.
- An explicit **Pause** or **Stop** (a phone call through KDE Connect, unplugged headphones) only ever pauses, never starts anything.
- Media in embedded players and cross-site frames counts too.

## Limitations

- Players built purely on Web Audio (some games, synths) have no media element to pause.
- Playback started from your desktop's media widget or from headphone buttons doesn't count as "started by you".

## Privacy

No data is collected and nothing leaves your browser. The extension has no permissions beyond running its script on web pages, which is where the media is.

## Development

- `extension/` is the extension itself (no build step).
- `python3 tests/run.py` runs the end-to-end tests in a throwaway headless Firefox (needs `firefox`, `pactl`). Pages play a near-silent tone into a temporary null audio sink, so nothing is heard.
- `sign.sh` signs a private (unlisted) build; `publish.sh` submits a public version to addons.mozilla.org. Both need AMO API credentials.
- Bump `version` in `extension/manifest.json` before either.

## License

[MIT](LICENSE)
