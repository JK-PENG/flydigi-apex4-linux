# OW2 Controller Profile Session Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an OW2 opt-in Steam launch mode that safely changes the installed relay from DualSense Edge to ordinary DualSense for the game process and verifies Edge restoration afterward.

**Architecture:** A new `apex4ds5.game_session` module owns fail-closed user-systemd and sysfs identity transitions. `tools/proton-game.py` keeps its current filter/exec path by default, but `--relay-profile dualsense` wraps the Proton child in that session and forwards termination signals so cleanup runs.

**Tech Stack:** Python 3 standard library, `unittest`, user systemd, Linux hidraw sysfs, existing `apex4-relay` script.

## Global Constraints

- OW2 is the only initially documented opt-in game; do not generalize the observed Edge behavior.
- Do not enable adaptive-trigger writes or send HID commands as part of profile switching.
- Preserve existing filter lists, argv boundaries, and default `os.execvpe` behavior.
- Refuse to launch when the installed Edge service is not the verified starting state.
- Use argv arrays only; do not add shell command construction or runtime dependencies.
- Do not touch the SteamOS host's existing dirty checkout or installed tree during software validation.
- Any actual game launch requires advance notice and holder confirmation.

---

### Task 1: Relay profile lifecycle

**Files:**
- Create: `apex4ds5/game_session.py`
- Create: `tests/test_game_session.py`

**Interfaces:**
- Consumes: installed `apex4-relay`, `systemctl --user is-active`, and hidraw `uevent` files.
- Produces: `RelayProfileSession(relay_script, run=..., sleep=..., sysfs_root=..., timeout=...)`, `RelaySessionError`, `EDGE_IDENTITY`, and `DUALSENSE_IDENTITY`.

- [ ] **Step 1: Write failing identity and preflight tests**

Create a temporary `hidrawN/device/uevent` containing both `HID_ID` and
`HID_NAME`, and assert that an active installed unit plus an inactive manual
unit is accepted only for the exact project Edge identity:

```python
def test_preflight_requires_project_edge_and_no_manual_relay(self):
    fake = FakeCommands(daily=True, manual=False)
    write_uevent(self.sysfs, "hidraw0", "0003:0000054C:00000DF2",
                 "Apex 4 (DualSense Edge)")
    session = game_session.RelayProfileSession(
        "/installed/apex4-relay", run=fake, sleep=lambda _: None,
        sysfs_root=self.sysfs, timeout=0)
    session.preflight()
    fake.manual = True
    with self.assertRaises(game_session.RelaySessionError):
        session.preflight()
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `python3 -m unittest tests.test_game_session -v`

Expected: import failure because `apex4ds5.game_session` does not exist.

- [ ] **Step 3: Implement exact project identity matching and preflight**

Add immutable identities and read only the expected uevent keys:

```python
EDGE_IDENTITY = ("0003:0000054C:00000DF2", "Apex 4 (DualSense Edge)")
DUALSENSE_IDENTITY = ("0003:0000054C:00000CE6", "Apex 4 (DualSense)")

def identity_present(sysfs_root, identity):
    for path in pathlib.Path(sysfs_root).glob("hidraw*/device/uevent"):
        fields = dict(line.split("=", 1) for line in path.read_text().splitlines()
                      if "=" in line)
        if (fields.get("HID_ID"), fields.get("HID_NAME")) == identity:
            return True
    return False
```

`preflight()` must require `flydigi-apex4.service` active,
`apex4-relay-manual.service` inactive, and `EDGE_IDENTITY` present. Convert
missing executables and nonzero command results into phase-specific
`RelaySessionError` messages.

- [ ] **Step 4: Run the focused test and verify GREEN**

Run: `python3 -m unittest tests.test_game_session -v`

Expected: the identity/preflight tests pass.

- [ ] **Step 5: Write failing switch, timeout, and restore tests**

Use a fake command runner that updates unit state and replaces temporary uevent
files when it observes these exact argv arrays:

```python
[relay_script, "start", "--", "--emulate", "dualsense"]
[relay_script, "stop"]
["systemctl", "--user", "start", "flydigi-apex4.service"]
```

Assert successful command ordering; assert that a missing DualSense identity
raises before a child could be launched; and assert Edge restoration is still
attempted after that timeout.

- [ ] **Step 6: Run the lifecycle tests and verify RED**

Run: `python3 -m unittest tests.test_game_session -v`

Expected: failures because session enter/exit and restoration are absent.

- [ ] **Step 7: Implement the context-managed lifecycle**

`__enter__` calls `preflight()`, sets `_restore_required = True` before the
first mutating command, starts the transient relay, and waits up to `timeout`
for `DUALSENSE_IDENTITY`. If entry fails after mutation, it calls `restore()`
before re-raising. `__exit__` always calls `restore()`.

`restore()` runs the stop/start commands, then waits for `EDGE_IDENTITY`. It is
idempotent after a confirmed restore. If both switching and restoring fail,
raise a `RelaySessionError` that includes both phases without suppressing the
fact that the game was never launched.

- [ ] **Step 8: Run Task 1 tests and the full suite**

Run: `python3 -m unittest tests.test_game_session -v`

Expected: all Task 1 tests pass.

Run: `python3 -m unittest discover -s tests`

Expected: all tests pass.

- [ ] **Step 9: Commit Task 1**

```bash
git add apex4ds5/game_session.py tests/test_game_session.py
git commit -m "feat: add fail-closed relay profile sessions"
```

### Task 2: Steam wrapper integration

**Files:**
- Modify: `tools/proton-game.py`
- Modify: `tests/test_proton_game.py`

**Interfaces:**
- Consumes: `RelayProfileSession` from Task 1 and the existing filtered game environment.
- Produces: `--relay-profile {unchanged,dualsense}`, `run_child(command, environ, popen=...)`, and `run_profiled_command(...) -> int`.

- [ ] **Step 1: Write failing parser/preview safety tests**

Add subprocess tests asserting that preview mode with `--relay-profile
dualsense` reports Edge -> DualSense -> Edge but starts no command, and that
`--probe` plus this profile exits 2 with a clear incompatibility message.

```python
result = subprocess.run(
    [sys.executable, str(TOOL), "--relay-profile", "dualsense", "--",
     "/no/such/game"], capture_output=True, text=True)
self.assertEqual(result.returncode, 0)
self.assertIn("Edge -> DualSense -> Edge", result.stdout)
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `python3 -m unittest tests.test_proton_game.ProtonGameTests -v`

Expected: argparse rejects the new option or the preview line is absent.

- [ ] **Step 3: Add the option without changing default execution**

Parse `--relay-profile` with choices `unchanged` and `dualsense`, defaulting to
`unchanged`. Reject `dualsense` with `--probe`. In preview mode print the
transition plan and return before resolving service state. Leave the current
`os.execvpe` branch unchanged for the default profile.

- [ ] **Step 4: Verify parser/preview GREEN**

Run: `python3 -m unittest tests.test_proton_game.ProtonGameTests -v`

Expected: existing and new preview tests pass.

- [ ] **Step 5: Write failing profiled child lifecycle tests**

Import the tool as the existing tests do, inject a fake session factory and
fake `Popen`, and assert:

```python
events == ["session-enter", "child-start", "child-wait", "session-exit"]
```

The fake child must receive the exact argv and filtered environment, return code
17 must be preserved, and an exception from `wait()` must still record
`session-exit`.

- [ ] **Step 6: Run lifecycle tests and verify RED**

Run: `python3 -m unittest tests.test_proton_game.ProtonGameTests -v`

Expected: failures because `run_child` and `run_profiled_command` are missing.

- [ ] **Step 7: Implement child execution and signal forwarding**

`run_child()` starts `subprocess.Popen(command, env=environ)` without a shell.
Temporarily install SIGINT/SIGTERM handlers that forward the same signal to the
child, restore the previous handlers in `finally`, and translate a negative
child signal status to `128 + signal_number`.

`run_profiled_command()` resolves `apex4-relay` one directory above `tools/`,
enters `RelayProfileSession`, calls `run_child`, and lets the context restore
Edge before returning the child status. Catch `RelaySessionError` in `main()`,
print only the bounded error message to stderr, and return 1.

- [ ] **Step 8: Verify Task 2 and full regression suite**

Run: `python3 -m unittest tests.test_proton_game -v`

Expected: all wrapper tests pass.

Run: `python3 -m unittest discover -s tests`

Expected: all tests pass with no warnings.

- [ ] **Step 9: Commit Task 2**

```bash
git add tools/proton-game.py tests/test_proton_game.py
git commit -m "feat: switch OW2 relay identity for one game session"
```

### Task 3: Documentation and non-game SteamOS validation

**Files:**
- Modify: `README.md`
- Modify: `docs/CONTINUE.md`
- Modify: `docs/VALIDATION.md`
- Modify: `docs/evidence/README.md`
- Create after fresh remote evidence: `docs/evidence/2026-09-20-controller-profile-session.txt`

**Interfaces:**
- Consumes: the new launch flag and observed remote unit/identity transitions.
- Produces: an OW2-only launch-option recipe, recovery instructions, and sanitized evidence.

- [ ] **Step 1: Update user-facing instructions**

Document this OW2 launch option:

```text
/home/deck/.local/share/flydigi-apex4/tools/proton-game.py --run --relay-profile dualsense -- %command%
```

State that other games remain Edge by default, Edge-only back buttons are absent
during OW2, trigger writes retain the existing opt-in, and manual recovery is:

```sh
systemctl --user stop apex4-relay-manual.service
systemctl --user restart flydigi-apex4.service
```

- [ ] **Step 2: Run static and local regression checks**

Run:

```bash
python3 -m unittest discover -s tests
python3 -m py_compile apex4-ds5 apex4ds5/*.py apex4ds5/_ds5/*.py tools/*.py
bash -n install.sh apex4-autostart apex4-relay
git diff --check
```

Expected: every command exits 0.

- [ ] **Step 3: Validate in the isolated SteamOS test tree without launching a game**

Copy only the changed source/test files to the existing independent diagnostic
tree, not the dirty checkout or installed prefix. Run the Python tests and
compile checks there. Exercise preview mode only; it must print the profile plan
without changing either service.

Then use a harmless child command with an isolated copied relay and
`adaptive_triggers=false` only if the installed service state can be preserved.
Record exact before/temporary/after unit names and virtual identities. Stop if
the starting state is not one active installed Edge relay.

- [ ] **Step 4: Sanitize and index evidence**

The evidence file may include unit names, Sony VID/PID identities, return codes,
and timestamps. It must exclude credentials, network addresses, Steam account
ids, controller identifiers, and user-specific device paths.

- [ ] **Step 5: Commit documentation and evidence**

```bash
git add README.md docs/CONTINUE.md docs/VALIDATION.md docs/evidence/README.md \
  docs/evidence/2026-09-20-controller-profile-session.txt
git commit -m "docs: document OW2 controller profile switching"
```

- [ ] **Step 6: Stop before actual OW2 launch**

Report the software and non-game transition evidence. Announce that the next
step will visibly launch OW2 and switch Edge -> DualSense -> Edge, then wait for
explicit user confirmation. This launch does not itself authorize unrestricted
physical adaptive-trigger writes.
