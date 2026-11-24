"""Power Board Rev3 bench helpers: KA3005P + DHO804 (drivers reused from the DC Load Box project) and the e-load
through the e-load GUI's localhost command port (TCP 127.0.0.1:50555).

Safety model
  * Hard PSU limits here: V <= 22.0 V (25.7 V only with allow_ovp_test=True), I <= 2.0 A.
  * abort(): e-load OFF -> PSU OUT0, each step wrapped; registered with atexit.
  * A monitor thread polls the PSU at ~4 Hz; it aborts on CC mode (unless allowed), I above the step's trip
    current, V above the limit, or stale readings.
"""
from __future__ import annotations

import atexit
import csv
import json
import socket
import sys
import threading
import time
from pathlib import Path

DCLOAD = Path(r"G:/Other computers/MBA 1/Documents/Project/01 Hardware/DC Load Box/bench_test")
sys.path.insert(0, str(DCLOAD))
from bench.config import find_serial, find_scope, PSU_VIDPID          # noqa: E402
from bench.instruments.ka3005p import KA3005P                         # noqa: E402
from bench.instruments.dho804 import DHO804                           # noqa: E402

BENCH = Path(__file__).resolve().parents[1]
RESULTS = BENCH / "results"
SCOPE_DIR = BENCH / "scope"
V_LIMIT = 22.0
V_LIMIT_OVP_TEST = 25.7
I_LIMIT = 2.0


class Aborted(RuntimeError):
    pass


class ELoadRemote:
    def __init__(self, host="127.0.0.1", port=50555):
        self.addr = (host, port)

    def cmd(self, line: str, timeout=3.0) -> str:
        with socket.create_connection(self.addr, timeout=timeout) as s:
            s.sendall((line + "\n").encode())
            f = s.makefile("r")
            return f.readline().strip()

    def status(self) -> dict:
        return json.loads(self.cmd("STATUS"))

    def healthy(self) -> dict:
        """Raise unless the GUI has a live serial link (last good poll < 1 s ago)."""
        st = self.status()
        if not st.get("connected") or st.get("age", 99) > 1.0:
            raise RuntimeError(f"e-load link not healthy: connected={st.get('connected')} age={st.get('age')} s")
        return st

    def on(self, amps: float, vdut: float = 5.0):
        self.healthy()
        r = self.cmd(f"ON {amps:.3f} {vdut:g}")
        if r != "OK":
            raise RuntimeError(f"e-load ON: {r}")

    def set(self, amps: float):
        r = self.cmd(f"SET {amps:.3f}")
        if r != "OK":
            raise RuntimeError(f"e-load SET: {r}")

    def off(self):
        return self.cmd("OFF")

    def wait_ready(self, text: str, check=None, timeout=900):
        """Show a prompt and block until the tester presses READY (button or SPACE) in the GUI."""
        self.cmd("READYCLR")
        self.msg(text + "   ->  press READY when set")
        t0 = time.time()
        while time.time() - t0 < timeout:
            if check:
                check()
            if self.cmd("READY?") == "1":
                return True
            time.sleep(0.2)
        raise TimeoutError("tester did not press READY")

    def ask_number(self, text: str, lo=None, hi=None, check=None, timeout=1800) -> float:
        """Ask the tester for a number in the GUI entry box; re-asks if it is not a number or out of [lo, hi]."""
        q = text
        rejected = None
        t0 = time.time()
        while time.time() - t0 < timeout:
            self.cmd("ASK " + q)
            while time.time() - t0 < timeout:
                if check:
                    check()
                a = self.cmd("ANSWER?")
                if a.startswith("A "):
                    break
                time.sleep(0.2)
            try:
                x = float(a[2:].replace(",", "."))
            except ValueError:
                q = f"NOT A NUMBER ('{a[2:]}'). {text}"
                continue
            if ((lo is not None and x < lo) or (hi is not None and x > hi)) and x != rejected:
                rejected = x
                q = f"{x:g} looks wrong (expect {lo}..{hi}) - re-measure, or type it again to accept. {text}"
                continue
            return x
        raise TimeoutError("no answer")

    def msg(self, text: str):
        """Large prompt line in the GUI window (tester instructions while a script runs)."""
        try:
            self.cmd("MSG " + text)
        except Exception:
            pass


class Run:
    """One logged test run: results/<date>_<time>_<name>/ with data.csv, meta.json, notes, scope PNGs."""

    def __init__(self, name: str):
        self.dir = RESULTS / f"{time.strftime('%Y-%m-%d_%H%M%S')}_{name}"
        self.dir.mkdir(parents=True, exist_ok=True)
        self._csv = None
        self._w = None
        self.meta = {"name": name, "start": time.strftime("%Y-%m-%d %H:%M:%S")}

    def row(self, **kv):
        kv = {"t": round(time.time(), 3), **kv}
        if self._w is None:
            self._csv = open(self.dir / "data.csv", "w", newline="")
            self._w = csv.DictWriter(self._csv, fieldnames=list(kv.keys()), extrasaction="ignore")
            self._w.writeheader()
        self._w.writerow(kv)
        self._csv.flush()
        print("  ", {k: v for k, v in kv.items() if k != "t"})

    def note(self, text: str):
        print(text)
        with open(self.dir / "notes.txt", "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%H:%M:%S')}  {text}\n")

    def close(self):
        self.meta["end"] = time.strftime("%Y-%m-%d %H:%M:%S")
        (self.dir / "meta.json").write_text(json.dumps(self.meta, indent=2, default=str))
        if self._csv:
            self._csv.close()


class Bench:
    def __init__(self, scope=True, eload=True):
        self.psu = KA3005P(find_serial(*PSU_VIDPID))
        self.scope = None
        if scope:
            import pyvisa
            self.rm = pyvisa.ResourceManager()
            self.scope = DHO804(find_scope(self.rm), self.rm)
        self.eload = ELoadRemote() if eload else None
        self.v_max = V_LIMIT
        self.i_trip = 0.10            # monitor aborts above this (A), set per step
        self.allow_cc = False
        self.latest: dict = {}
        self.abort_reason = None
        self._stop = threading.Event()
        atexit.register(self.abort, "atexit")
        self._t = threading.Thread(target=self._monitor, daemon=True)
        self._t.start()

    # ------------------------------------------------------------ safety
    def abort(self, reason="abort"):
        if reason != "atexit" and self.abort_reason is None:
            self.abort_reason = reason
        if self.eload:
            try:
                self.eload.off()
            except Exception as e:
                print(f"[abort] e-load OFF failed: {e}")
        try:
            self.psu.write("OUT0", lock_timeout=1.0)
        except Exception as e:
            print(f"[abort] PSU OUT0 failed: {e}")
        if reason != "atexit":
            print(f"[ABORT] {reason}: e-load OFF, PSU OUT0")

    def _monitor(self):
        last_ok = time.time()
        while not self._stop.is_set():
            try:
                vmax, itrip = self.v_max, self.i_trip          # limits in force when this reading is taken
                v, i, st = self.psu.vout(), self.psu.iout(), self.psu.status()
                vmax, itrip = max(vmax, self.v_max), max(itrip, self.i_trip)
                self.latest = {"t": time.time(), "v": v, "i": i, **st}
                last_ok = time.time()
                if st["output"] and self.abort_reason is None:
                    if v > vmax + 0.15:
                        self.abort(f"PSU V {v:.2f} > {vmax}")
                    elif i > itrip:
                        self.abort(f"PSU I {i:.3f} A > trip {itrip:.3f} A")
                    elif not st["cv"] and not self.allow_cc:
                        time.sleep(0.15)                      # confirm, CC can blink during a step
                        if not self.psu.status()["cv"]:
                            self.abort("PSU entered CC (current limit)")
            except Exception as e:
                if time.time() - last_ok > 2.0:
                    self.abort(f"PSU readings stale ({e})")
            self._stop.wait(0.25)

    def check(self):
        if self.abort_reason:
            raise Aborted(self.abort_reason)

    def sleep(self, s: float):
        end = time.time() + s
        while time.time() < end:
            self.check()
            time.sleep(0.05)

    def close(self):
        self._stop.set()
        self._t.join(timeout=1)
        atexit.unregister(self.abort)
        self.psu.close()
        if self.scope:
            self.scope.close()

    # ------------------------------------------------------------ PSU
    def psu_set(self, v: float, i: float, allow_ovp_test=False):
        vmax = V_LIMIT_OVP_TEST if allow_ovp_test else V_LIMIT
        if v > vmax or i > I_LIMIT:
            raise ValueError(f"PSU request {v} V / {i} A outside {vmax} V / {I_LIMIT} A")
        target_cap = max(v, 0.0) if not allow_ovp_test else vmax
        going_down = self.psu.status()["output"] and self.psu.vout() > v + 0.3
        self.v_max = max(self.v_max, target_cap) if going_down else target_cap
        self.psu.set_i(i)
        self.psu.set_v(v)
        if going_down:                        # keep the old ceiling until the output has actually come down
            t0 = time.time()
            while self.psu.vout() > v + 0.1 and time.time() - t0 < 15:
                self.check()
                time.sleep(0.2)
            self.v_max = target_cap

    def psu_on(self):
        self.check()
        self.psu.output(True)

    def psu_off(self):
        self.psu.output(False)

    def psu_read(self, n=4, gap=0.3) -> dict:
        vs, is_ = [], []
        for _ in range(n):
            self.check()
            vs.append(self.psu.vout()); is_.append(self.psu.iout())
            time.sleep(gap)
        return {"psu_v": round(sum(vs) / n, 3), "psu_i": round(sum(is_) / n, 4), "psu_i_max": max(is_)}

    # ------------------------------------------------------------ scope
    def scope_means(self, chs=(1, 2, 3, 4)) -> dict:
        return {f"ch{c}": round(self.scope.item("VAVG", c), 4) for c in chs}

    def shot(self, run: Run, name: str):
        SCOPE_DIR.mkdir(exist_ok=True)
        p1 = run.dir / f"{name}.png"
        self.scope.screenshot(p1)
        (SCOPE_DIR / f"{name}.png").write_bytes(p1.read_bytes())
        run.note(f"scope capture saved: scope\\{name}.png")
