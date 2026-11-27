"""Serves reports about Live's Python API at http://127.0.0.1:31415/.

Read-only: it accepts no code or data, only GET requests for the fixed
reports in reports.py. It listens on this computer only.
"""

import queue
import socket
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import Live

from . import reports

PORT = 31415

ROUTES = {
    "/": reports.page,
    "/api.json": reports.api_json,
    "/python-vs-max.txt": reports.python_vs_max,
}

# How long a request waits for Live to start the report, and again to finish.
TIMEOUT = 60.0

# A Host outside these is a DNS-rebinding web page reaching us under its own
# name.
LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")

_TEXT = "text/plain; charset=utf-8"


class LiveApiProbe:
    """The control surface: owns the server and runs its reports."""

    def __init__(self, c_instance):
        self._c_instance = c_instance
        self._jobs = queue.Queue()
        self._server = None
        self._start_server()

    def _log(self, message):
        self._c_instance.log_message("[Live API Probe] " + str(message))

    def _start_server(self):
        # Binding alone can't tell: on macOS a bind to 127.0.0.1 succeeds even
        # when another program listens on every address.
        if _answers(PORT):
            self._log("port %d is in use, not listening" % PORT)
            return

        try:
            server = _Server(("127.0.0.1", PORT), _Handler)
        except OSError as err:
            self._log("could not bind port %d: %s" % (PORT, err))
            return

        server.jobs = self._jobs
        server.log = self._log
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self._server = server
        self._log("listening on http://127.0.0.1:%d" % PORT)

    # --- Live's main thread ---------------------------------------------

    def update_display(self):
        """Live calls this about 10 times a second. Reports run here."""
        while True:
            try:
                job = self._jobs.get_nowait()
            except queue.Empty:
                break
            job.run()

        # Live holds Python's lock between calls, so the server thread only
        # gets to run while we sleep.
        time.sleep(0.001)

    def disconnect(self):
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None

    # --- the rest of what Live expects a control surface to have ---------

    def connect_script_instances(self, instances):
        pass

    def can_lock_to_devices(self):
        return False

    def lock_to_device(self, device):
        pass

    def unlock_from_device(self, device):
        pass

    def toggle_lock(self):
        pass

    def set_appointed_device(self, device):
        pass

    def suggest_input_port(self):
        return ""

    def suggest_output_port(self):
        return ""

    def suggest_map_mode(self, cc_no, channel):
        return Live.MidiMap.MapMode.absolute

    def supports_pad_translation(self):
        return False

    def show_message(self, message):
        self._c_instance.show_message(message)

    def request_rebuild_midi_map(self):
        self._c_instance.request_rebuild_midi_map()

    def build_midi_map(self, midi_map_handle):
        pass

    def receive_midi(self, midi_bytes):
        pass

    def handle_sysex(self, midi_bytes):
        pass

    def refresh_state(self):
        pass

    def is_extension(self):
        return False


class _Job:
    """One requested report, waiting for Live's main thread."""

    def __init__(self, report):
        self._report = report
        self._lock = threading.Lock()
        self._started = threading.Event()
        self._abandoned = False
        self._reply = queue.Queue(1)

    def run(self):
        with self._lock:
            # The client stopped waiting.
            if self._abandoned:
                return
            self._started.set()

        try:
            content_type, text = self._report()
            self._reply.put((200, content_type, text))
        except Exception:
            self._reply.put((500, _TEXT, traceback.format_exc()))

    def wait(self):
        """The reply as (status, content type, text). Called on a server thread."""
        if not self._started.wait(TIMEOUT):
            with self._lock:
                if not self._started.is_set():
                    self._abandoned = True
                    return 504, _TEXT, "Live didn't start the report in time.\n"

        try:
            return self._reply.get(timeout=TIMEOUT)
        except queue.Empty:
            return 504, _TEXT, "Live didn't finish the report in time.\n"


class _Server(ThreadingHTTPServer):
    # On Windows this would let a second program bind the same port.
    allow_reuse_address = sys.platform != "win32"
    daemon_threads = True


class _Handler(BaseHTTPRequestHandler):
    # Seconds a stalled connection may hold a thread.
    timeout = 10

    def do_GET(self):
        if not self._allowed():
            return

        report = ROUTES.get(urlsplit(self.path).path)
        if report is None:
            pages = "\n".join(sorted(ROUTES))
            self._send(404, _TEXT, "No such page. Try:\n%s\n" % pages)
            return

        job = _Job(report)
        self.server.jobs.put(job)
        self._send(*job.wait())

    def _allowed(self):
        """Refuse requests another website's page makes. False if refused."""
        # A browser sends Sec-Fetch-Site: "none" for an address the user
        # opened, "same-origin" for a link between our own pages. Following a
        # link from another site (Sec-Fetch-Mode: "navigate") is fine too: that
        # site can't read the page it leads to.
        if (
            self.headers.get("Sec-Fetch-Site") not in (None, "none", "same-origin")
            and self.headers.get("Sec-Fetch-Mode") != "navigate"
        ):
            error = "Requests from other websites are refused.\n"
        elif _hostname(self.headers.get("Host")) not in LOOPBACK_HOSTS:
            error = "Host must be 127.0.0.1 or localhost.\n"
        else:
            return True
        self._send(403, _TEXT, error)
        return False

    def _send(self, status, content_type, text):
        data = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(data)

    def log_request(self, code="-", size="-"):
        # Not logged: Live's log call isn't meant for a server thread.
        pass

    def log_message(self, fmt, *args):
        self.server.log("http: " + (fmt % args))


def _answers(port):
    """Whether something already accepts connections on 127.0.0.1:`port`."""
    try:
        socket.create_connection(("127.0.0.1", port), timeout=0.25).close()
        return True
    except OSError:
        return False


def _hostname(host):
    """The lowercase hostname of a Host header, or None when it has none."""
    try:
        return urlsplit("//" + host).hostname if host else None
    except ValueError:
        return None
