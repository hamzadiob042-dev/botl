import json, os, subprocess, sys, tempfile
TOOL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "runner3mh.py")
TMP = tempfile.mkdtemp(prefix="3mh-")
ok = fail = 0


def run(args, stdin=None, timeout=180):
    p = subprocess.run([sys.executable, TOOL, *args], input=stdin, capture_output=True,
                       text=True, timeout=timeout, cwd=TMP)
    return p.returncode, p.stdout, p.stderr


def check(name, cond, detail=""):
    global ok, fail
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)
    print(("  PASS  " if cond else "  FAIL  ") + name + ("" if cond else f" :: {detail[:220]}"))


rc, out, err = run(["run", "-c", "print('SMOKE-OK')", "-q"])
check("run -c", rc == 0 and "SMOKE-OK" in out, out + err)

p = os.path.join(TMP, "ar.py")
open(p, "w", encoding="utf-8").write("print('مرحبا 3MH')\n")
rc, out, err = run(["run", p, "-q"])
check("arabic utf8", rc == 0 and "مرحبا 3MH" in out, out + err)

rc, out, err = run(["run", "-c", "import sys;print(sys.argv[1:])", "--args", "--n 5 x", "-q"])
check("argv passthrough", "['--n', '5', 'x']" in out, out + err)

rc, out, err = run(["run", "-c", "a=input();b=input();print(int(a)+int(b))", "--stdin", "20\\n22", "-q"])
check("stdin prefeed", rc == 0 and out.strip() == "42", out + err)

rc, out, err = run(["run", "-c", "print('piped')", "-q"], stdin="9\n")
check("piped stdin", rc == 0 and "piped" in out, out + err)

proj = os.path.join(TMP, "proj")
os.makedirs(proj)
open(proj + "/main.py", "w").write("from lib import double\nprint(double(21))\nprint(open('d.txt').read().strip())\n")
open(proj + "/lib.py", "w").write("def double(x): return x*2\n")
open(proj + "/d.txt", "w").write("data-ok\n")
rc, out, err = run(["run", "-d", proj, "-q"])
check("multi-file project", rc == 0 and "42" in out and "data-ok" in out, out + err)

rc, out, err = run(["run", "-c", "raise SystemExit(7)", "-q"])
check("remote exit code 7", rc == 7, f"rc={rc}")

rc, out, err = run(["run", "-c", "1/0", "-q"])
check("traceback + exit 1", rc == 1 and "ZeroDivisionError" in out + err, out + err)

rc, out, err = run(["run", "-c", "print('j')", "--json"])
d = json.loads(out or "{}")
check("--json contract", rc == 0 and d.get("ok") is True and d.get("local_exit_code") == 0, out + err)

rc, out, err = run(["run", "-c", "import time;time.sleep(60)", "--timeout", "6", "-q"])
check("local timeout 124", rc == 124, f"rc={rc}")

rc, out, err = run(["run", "-c", "for i in range(60000): print('y'*60,i)", "--timeout", "60", "-q"])
check("2MB output kill -> 137", rc == 137, f"rc={rc}")

rc, out, err = run(["info", "--json"])
d = json.loads(out or "{}")
check("info probe", rc == 0 and str(d.get("environment", {}).get("python", "")).startswith("3.12"), out[:200] + err)

png = os.path.join(TMP, "b.png")
open(png, "wb").write(bytes.fromhex("89504e470d0a1a0a") + b"\x00" * 32)
bp = os.path.join(TMP, "b.py")
open(bp, "w").write("d=open('b.png','rb').read();print('MAGIC',d[:4].hex(),len(d))\n")
rc, out, err = run(["run", bp, png, "-q"])
check("binary asset injection", rc == 0 and "MAGIC 89504e47 40" in out, out + err)

rc, out, err = run(["share", proj + "/main.py", "--days", "1", "--json"])
sid = json.loads(out or "{}").get("share_id", "") if rc == 0 else ""
check("share", rc == 0 and bool(sid), out + err)
if sid:
    o = os.path.join(TMP, "pulled")
    rc, out, err = run(["pull", sid, "-o", o, "--json"])
    check("pull", rc == 0 and os.path.exists(os.path.join(o, "main.py")), out + err)

rc, out, err = run(["repl", "--delay", "0.7", "--grace", "3"], stdin="2**8\nprint('repl-marker')\nexit()\n", timeout=150)
check("remote repl", rc == 0 and "256" in out and "repl-marker" in out, out[:200] + err)

rc, out, err = run(["run", "-c", "print('x')", "--host", "https://does-not-exist.invalid", "--retries", "1"])
check("bad host -> exit 2", rc == 2, f"rc={rc} {err[:120]}")

print(f"\n{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
