# X language switcher v1.0 ("xswitcher")
Xswitcher is the fully customizable low-level keyboard helper for X.Org-based Linux desktops.  
It consists of two main parts: low-level keylogger and the virtual keyboard.  
On each key up/down event, xswitcher checks the last events chain against configured regex-based patterns.  
If one matches, xswitcher triggers the associated action. Action chains can be joined from simple actions.  
Look at TOML-based explained config file "xswitcher.conf" for further details.

## Retype
One of the most powerful actions of xswitcher is to retype the collected event buffer
after switching the language. Because of it's low-level nature, it may know nothing about layout details.  
So, xswitcher does nothing strange, in comparison with punto switcher on windows.  
It just sends a number of BackSpaces to wipe the last input, then calls language switcher
(internal, via X API, or external, via call of the configured program), an then retypes the same
keyboard events by means of virtual keyboard.

## Gnome is the pain
Note that the users of actual gnome-based shells can't use the XOrg embedded language switcher.
Due to the gnome built-in bug, X language API is broken by gnome since 2011.
However, there's the workaround. Look under the "gnome3" subfolder for customized config file and the simple helper "switch.gnome".
The helper header contains the brief instruction on how to deal with the https://github.com/lyokha/g3kb-switch.git

## Precompiled xswitcher for the beginners
The statically compiled binary lays under "bin" folder.  
The unexperienced users *(except of those who used gnome-based interfaces, e.g. ubuntu)* can just download this binary.  
Then put it under e.g. "/usr/local/bin" path and make it executable:  

    sudo chown root:root /usr/local/bin/xswitcher
    sudo chmod +xs /usr/local/bin/xswitcher

Note the sticky bit "+s" in this example. Being the low-level keylogger, xswitcher needs the access to "/dev/input/" devices.  
Someone can make xswitcher slightly less dangerous by adding the privilege-separated code.  
Or You yourself can try add your GUI user to "input" group (but I'm not sure it's enough to attach the virtual keyboard).  
All improvements are welcome.

Also note that, being an honest keylogger by nature, xswitcher can be of course configured to do something strange.  
E.g. you can configure it to email all the input to e.g. "fbi@usa.gov". Nobody bans.

## CLI
There are a number of helpful CLI flags:

    xswitcher -h
    Usage of :
      -c, --conf string   Non-default config location (default "/etc/xswitcher/xswitcher.conf")
      -d, --debug         Debug log level
      -t, --test          Only output all key events to STDERR. No actions.
      -v, --verbose       Increase log level to NOTICE

Use "-v" or even "-d" to debug when You implements any config changes.  
Use "-t" to collect the keyboard events string to construct Your custom actions.

## Respawn
This version of xswitcher do the scan of input devices only once (on it's launch).  
But there is the internal "respawn" action in case You connects new keyboard/mouse.  
By default, the long press of "Scroll lock" triggers "respawn". (Respawn does the complete self-restart).

## Adding a language

Translations live under `internal/l10n/locales/`. One JSON file per
language, named by the BCP-47 base tag (`en.json`, `ru.json`, `de.json`).
Region variants collapse to their base (`pt_BR` and `pt` both resolve to
`pt`), so keep one file per language unless you actually need divergent
translations for two regions.

Every catalogue MUST define two meta-keys that name the language itself:

    {
      "language.name": "<endonym shown in the picker>",
      "language.english": "<same language named in English>"
    }

The picker displays `<name> (<english>)` when they differ and just
`<name>` when they are identical. A catalogue without these two keys still
loads but shows its file code instead of a human-readable label.

Every other key is the string passed to `l10n.X("key", "English literal")`
in the source. The English value in `en.json` MUST be byte-identical to the
literal at the call site; `go test ./internal/l10n` enforces this parity
and also checks that every non-English catalogue carries the same set of
keys and the same `{{.Placeholder}}` names as English. Run it after any
catalogue edit -- it is the drift guard.

Plurals use `l10n.XN("key", "other-form", count, ...)`. The JSON entry
uses go-i18n plural forms (`one`, `few`, `many`, `other`); Russian gets
`one/few/many/other` automatically via `x/text/plural`.

Locale resolution order:

1. `[GUI] Language` in the config (set by the GUI picker).
2. `XSWITCHER_LANG` environment variable (handy for systemd units:
   `Environment=XSWITCHER_LANG=ru`).
3. OS locale (`LC_ALL` / `LC_MESSAGES` / `LANG`, with `LANGUAGE`
   overriding when the slot is not `C`/`POSIX`).
4. English fallback.

An unknown or empty code at any step is skipped; an unknown explicit
choice in `[GUI] Language` is rejected so a typo cannot silently pin
the UI to the wrong file.

## Themes

The GUI ships three built-in choices -- `system`, `dark`, `light` -- and any
number of your own. A theme is a JSON file under the user config directory:

    ~/.config/xswitcher/themes/<name>.json

(on Windows: `%APPDATA%\xswitcher\themes`; override the whole directory with
the `XSWITCHER_THEMES_DIR` environment variable.) The picker in the About tab
lists the built-ins plus every `*.json` basename found there, applies the
choice immediately, and persists it as `[GUI] Theme` through the daemon, so it
survives a restart and is read before the first widget is built.

A file may set any subset of two blocks; everything it omits comes from the
Fyne palette of the chosen `variant`:

    {
      "variant": "dark",
      "name": "Neon",
      "colors": {
        "background": "#101418ff",
        "primary": "#00e5b0ff",
        "foreground": "#e6edf3ff"
      },
      "sizes": {
        "text": 14,
        "padding": 8,
        "inputRadius": 6
      }
    }

`variant` is `"dark"` or `"light"` (anything else is treated as dark) and picks
the fallback palette. `colors` keys are Fyne theme color names (28 in total, for
example `background`, `foreground`, `primary`, `button`, `menuBackground`,
`inputBackground`, `hyperlink`, `error`), and values are hex with a leading
`#`: `#rrggbb` or `#rrggbbaa`.
`sizes` keys are Fyne theme size names (19 in total, for example `text`,
`padding`, `innerPadding`, `lineSpacing`, `inputRadius`, `scrollBar`) with
floating-point values in pixels.

A malformed file, a hex value the loader cannot parse, or a theme name that
tries to leave the themes directory (`..`, `/`, `\`) is refused: the picker
shows why and keeps the previous theme.

## How to build.
You must install (libX11-devel | libx11-dev) package for X bindings.  
* The package name may, of course, be different in Your distro.  
X calls are made through cgo, so a C compiler ("gcc" or "clang") must be present too.  
And, of course, you must have the working go environment.  
The module pins the toolchain exactly: `go 1.26.0` plus `toolchain go1.26.10`. That is not a style
choice, it is what `govulncheck` reports: on go1.24.13 the scan finds 29 vulnerabilities reachable from
this code (18 of them in the standard library), on go1.26.0 it still finds 28, and on go1.26.10 zero.
The stand images follow the same pin (`golang:1.26-trixie`), so a local run, the container and CI measure
the same compiler.  
Build from the repository root:

    go build -o xswitcher ./src/

Nothing else is required. "go.mod" resolves every dependency by itself, no "go get" round is needed.  
The virtual keyboard library is not fetched from the network either:

    replace github.com/micmonay/keybd_event => ./src/keybd_event/

points it at the sources kept under "src/keybd_event", where my "keybd_linux_export.go" already lives.  
(Unfortunately my pull request https://github.com/micmonay/keybd_event/pull/32 still stays unaccepted.)  
"embeddedConfig", "exec" and "scancodes" are imported through the module name "xswitcher", so they must not
be moved under "src/" as the earlier version of this instruction told You to do.

There is exactly one module in the repository: the "stand" helpers are part of it too, so the clipboard holder
the rig needs builds from the root as well.

    go build -o /tmp/cliphold ./stand/cliphold/

A second "go.mod" under "stand/" silently hides that package from the root module ("main module (xswitcher)
does not contain package xswitcher/stand/cliphold"), which is how the rig lost a check without going red.
Build output is never a source: "/bin/" is ignored, the rig writes its own "/w/bin/xswitcher-gui" at run time.

The resulting binary is not static: it links libX11 (and libxcb) dynamically, as any X desktop provides them.  
To strip it, as I do for the "bin" folder, add the linker flags:

    go build -o xswitcher -ldflags "-s -w" ./src/ && chmod +xs xswitcher

Put the config to "/etc/xswitcher/xswitcher.conf" (or just use embedded one)
and install xswitcher executable under "/usr/local/bin/" or where You prefer.

Make it executable, e.g. "chmod +xs /usr/local/bin/xswitcher", configure the autostart inside Your X GUI and enjoy.

## How to verify.
xswitcher is a keylogger on top of the kernel input layer, so an honest check needs "/dev/input" and "uinput",  
not a mocked keyboard. The "stand" folder holds the end-to-end rig that does exactly this inside one privileged  
Linux container. It builds the daemon, runs it, creates a *second* virtual keyboard through uinput as the source  
device, injects keys into it and then asserts on the EV_KEY stream xswitcher emits on its own keyboard:

* "go build", "go vet" and "go test ./..." pass;
* "HELLO" + Pause wipes 5 symbols, sends the layout shortcut and retypes the word;
* a focus loss in the middle of a word does not wipe the collected word (the buffers survive "None" focus);
* a lone LeftCtrl tap only cycles the layout, with no BackSpaces at all.

Run it from the repository root:

    bash stand/run-stand.sh

It needs docker (or podman) with "--privileged" and the "uinput" + "evdev" modules loaded on the host kernel.  
On Windows 11 with Docker Desktop those modules are built but not autoloaded in the "docker-desktop" VM, so  
"stand/setup-host.sh" loads them; it has to be re-run after every WSL VM restart. No desktop session, no  
full distro installation and no second machine are required. Set "DUMPLOG=1" to get the whole daemon log.

The same rig has a GUI half, and it is the half that watches a real key press instead of a config file:

    bash stand/run-gui-stand.sh

It runs 20 checks (G1..G8) and refuses to go green if the count shrinks, builds the daemon and the Fyne GUI
from the checkout it is pointed at, and reads the stamp back off the binary it produced:

    xswitcher --version          # -> "xswitcher v1.1.0 (2d66d12)", one line, no root and no config needed

That line is what a release asset is matched against, so an unstamped build stays visible as
"xswitcher dev (unknown)" instead of pretending to be a release.

What a container does and does not prove. Xvfb serves a multi-group keymap only when started with
"-noreset": every observer here (setxkbmap, xgroup, the eye) is a one-shot client, and without that flag
the loaded map is restored the moment the last client leaves -- measured as "groups 1" without the flag and
"groups 2" with it. With the flag the rig really moves the live server: check G4 of `stand/gui-stand.sh`
asserts both that the server answers "locked 1" and that the daemon's log carries
"XkbLockGroup(1) answered 1". What no container here proves is a compositor: the Wayland bypass is measured
on the emitted EV_KEY stream (checks W1/W2 of `stand/run.sh`), never inside a real Wayland session.

## KDE@Wayland: shit happens
Wayland cancels all the X groundwork for multi-language systems.
While Gnome forces it's own dbus-based API, KDE does nothing at all.
X-layer is just a stub built into the current KDE environment. It doesn't contain any real data.
So, the only common things are now the kernel-based "/dev/input" and virtual keyboard.
Window classes are gone together with the language API.

I wrote the "[Wayland]" crutch. It selects language via keyboard shortcuts.
For example, one can configure "Win+1" to select language #0 and "Win+2" to select language #1.
Then, in "xswitcher.conf":

    [Wayland]
     BypassX = true # Switch layouts via pre-configured keyboard shortcuts
     Layout0 = ["L_META:1", "1:1", "1:0", "L_META:0"] # Win+1
     Layout1 = ["L_META:1", "2:1", "2:0", "L_META:0"] # Win+2
     Delay = 50

* It takes about 50 ms to complete switching the keyboard layout in my KDE, so I set 50 as the default value.
* Up to 4 language shortcuts "Layout0"�"Layout3".

What the crutch actually emits is measured, not assumed. With the shipped `BypassX = true` and a word typed
on the wrong layout, the daemon writes exactly this shape to its own uinput keyboard (recorded 23.10 with
`stand/sniff.py`, asserted as W1/W2 in `stand/run.sh`):

    125:1  3:1  3:0  125:0        # L_META down, KEY_2 down/up, L_META up -- [Wayland] Layout1
    14:1 14:0  x5                 # one BackSpace per collected character
    25:1 25:0 33:1 33:0 ...       # the word replayed with the SAME evdev codes

Two consequences are worth knowing before filing a bug. The daemon does not re-encode the letters into
Cyrillic: it hands the desktop environment the shortcut and retypes the physical keys, so the translation is
done by whatever that shortcut selects. And nothing here observes the result -- if the real desktop uses a
different binding (GNOME's default is Super+Space, not Super+1/Super+2), the wipe and the replay still happen
while the layout never moves. Checks W1 and W2 are what keeps this honest: W1 counts `XkbLockGroup` in the
log and expects zero, W2 matches the replayed sequence against the configured `Layout1`.

## Packaging
I don't have enough time to maintain any distro package (rpm, dpkg, etc.).  
But it seems to be a good deed. So, everybody who is ready to do this job is welcome.

## About / Maintainer

This fork is maintained by **BaHooo** (bahooo22).
The audit, fixes and regression guards shipped on the `fix/code-audit-and-issues` branch were produced as a stacked PR against upstream `ds-voix/xswitcher`; the branch commits carry per-issue verdicts (#14 fixed here, #12 guarded and attributed to upstream `5fe6e3a`, #5 defect + feature, #13/#1 no code changes).

- GitHub: <https://github.com/bahooo22>
- Fork / working branch: <https://github.com/bahooo22/xswitcher/tree/fix/code-audit-and-issues>
- Upstream: <https://github.com/ds-voix/xswitcher>

## Conclusion
Please, don't be shy to report the bug if something in this README looks unclear.
