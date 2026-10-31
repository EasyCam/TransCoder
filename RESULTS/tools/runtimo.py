#!/usr/bin/env python3
"""macOS-safe `timeout` replacement (no coreutils dependency).
Usage: python3 runtimo.py <seconds> <cmd> [args...]  -> runs cmd, kills it (SIGTERM, later SIGKILL) at <seconds>.
"""
import signal, subprocess, sys, time

secs = float(sys.argv[1])
cmd = sys.argv[2:]
p = subprocess.Popen(cmd)
deadline = time.time() + secs
killed = False
try:
    while p.poll() is None:
        if time.time() > deadline:
            p.send_signal(signal.SIGTERM)
            killed = True
            t0 = time.time()
            while p.poll() is None and time.time() - t0 < 5:
                time.sleep(0.1)
            if p.poll() is None:
                p.kill()
            break
        time.sleep(0.2)
finally:
    sys.exit(p.poll() if p.poll() is not None else (124 if killed else 1))
