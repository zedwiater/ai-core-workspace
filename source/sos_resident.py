#!/usr/bin/env python3
"""The SOS resident: a small standalone loop whose only
job is the SOS minimum. The watchdog (in the dwell
service) updates the state log; this resident reads the
log and fires — on a limp episode, again while a fix
request is ignored, and on its own if the watchdog ever
goes silent. It survives the watchdog by design: separate
process, separate unit, no shared fate.

    python3 sos_resident.py
"""
import os
import socket
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.nice(10)

from core import dwell as dwell_mod  # noqa: E402
from core import notify as notify_mod  # noqa: E402
from core import sos as sos_mod  # noqa: E402

HOST = socket.gethostname()


def main():
    while True:
        try:
            sos_mod.heartbeat()
            state = sos_mod.load()
            cfg = dwell_mod.load_loop_config()
            for fire in sos_mod.evaluate(state, time.time(),
                                         cfg["dwell_s"]):
                text = sos_mod.compose(HOST, state, fire)
                sent = notify_mod.send(text)
                sos_mod.mark_fired(sent.get("ok"),
                                   sent.get("why", ""))
                dwell_mod.log_timeline(
                    {"kind": "sos", "fire": fire["kind"],
                     "sent": sent.get("ok"),
                     "why": sent.get("why", "")})
        except Exception:
            pass  # the resident itself never dies loudly
        time.sleep(sos_mod.LOOP_S)


if __name__ == "__main__":
    main()
