# Live API Probe

See what Ableton Live's Python API can do, straight from your own Live.

Live runs Python for its control surface scripts. This is a tiny control
surface that reads the API from the running Live and serves it to your browser:
every class, property, method and enum, with Live's built-in help text, and a
mark on everything Max for Live can't reach.

Nothing else to install: Live brings the Python.

To just browse the API without installing anything, see the saved copies for
recent Live versions at <https://adamjmurray.github.io/live-api-probe/>.

> **Safety:** the script is read-only. It accepts no code or data, only
> requests for its fixed reports, and it listens on your own computer only
> (`127.0.0.1`).

## Setup

1. Copy the `LiveApiProbe` folder into the `Remote Scripts` folder of your
   User Library. Create the `Remote Scripts` folder if it's missing. By
   default it's at:
   - macOS: `/Users/YOUR_USERNAME/Music/Ableton/User Library/Remote Scripts/`
   - Windows: `C:\Users\YOUR_USERNAME\Documents\Ableton\User Library\Remote Scripts\`

   If you moved your User Library, Live's settings show where it is, under
   **Library**.
2. Restart Live.
3. In Live's settings, open **Tempo & MIDI** and pick **LiveApiProbe** as a
   Control Surface. Leave Input and Output as None.
4. Open <http://127.0.0.1:31415/> in a browser.

## Reports

| Address              | What it is                                                                |
| -------------------- | ------------------------------------------------------------------------- |
| `/`                  | The API as a searchable page. Save it to keep a copy that works on its own |
| `/api.json`          | The same data as JSON                                                     |
| `/python-vs-max.txt` | The members Max for Live can't reach                                      |

Every report says which Live version it came from.

The page has a menu to show the whole Python API, only what Max for Live can
reach, or only what Python can reach and Max can't. In `api.json`, each
member's `max` says whether Max for Live can use it, and each class's `max`
whether Max can reach the class at all.

### What's new in a Live version

Save `api.json` from each version and diff the files:

```sh
curl -o api-12.3.json http://127.0.0.1:31415/api.json   # on the old Live
curl -o api-12.4.json http://127.0.0.1:31415/api.json   # on the new one
diff api-12.3.json api-12.4.json
```

On Windows, use `curl.exe` and compare with `fc api-12.3.json api-12.4.json`.

### Python vs. Max for Live

Max for Live's `LiveAPI` goes through Live's own Python package `_MxDCore`,
which lists every member Max may use and refuses the rest. The probe compares
the Python API with that list. It reads the list rather than asking Max, so
confirm a member in Max before relying on it.

## Publishing versions

`docs/` holds saved reports per Live version, with an index page, ready for
GitHub Pages (serve the `docs` folder). To add or refresh the running Live's
version (macOS):

```sh
./export
```

It saves the page, `api.json` and `python-vs-max.txt` into
`docs/<Live version>/` and rebuilds `docs/index.html`.

## Changing it

The reports are plain Python in `LiveApiProbe/reports.py`, and the page is
`LiveApiProbe/page.html`. Edit the copy in your User Library. A change to the
page shows when you reload it in the browser; a change to the Python needs a
Live restart. To add a report, write a function that returns a content type
and text, and add it to `ROUTES` in `probe.py`.

## Notes

- The port is `31415`, set at the top of `LiveApiProbe/probe.py` and in
  `export`.
- Messages from the script go to Live's `Log.txt`, marked `[Live API Probe]`.
- Tested on Live 12.4 and the Live 13 beta, on macOS and Windows.
- Not affiliated with Ableton.

## License

MIT
