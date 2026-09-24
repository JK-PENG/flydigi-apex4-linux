# SPDX-License-Identifier: MIT
"""State, deduplication, diagnostics, and reset lifecycle for ForceAdapt."""
import time

from . import forceadapt, trigger_translation


SIDE_LABELS = {"left": "L2", "right": "R2"}


class OneShotMildGate:
    """Allow one fixed right-side mild effect, then latch safely off."""

    def __init__(self, duration=1.0, clock=time.monotonic):
        self.duration = min(1.0, max(0.1, float(duration)))
        self.clock = clock
        self.active = False
        self.complete = False
        self.deadline = None

    def __call__(self, effect):
        if self.complete or effect.side != "right":
            return None
        if effect.mode == forceadapt.MODE_NORMAL:
            if not self.active:
                return None
            self.active = False
            self.complete = True
            self.deadline = None
            return forceadapt.normal("right")
        if self.active:
            return None
        self.active = True
        self.deadline = self.clock() + self.duration
        return forceadapt.resistance("right", 60, 40)

    def expire(self, manager):
        if (not self.active or self.deadline is None
                or self.clock() < self.deadline):
            return None
        self.active = False
        self.complete = True
        self.deadline = None
        return manager.clear_all("one-shot mild safety timeout", force=True)

    def abort(self):
        self.active = False
        self.complete = True
        self.deadline = None


class BoundedDynamicGate:
    """Permit a few R2 resistance cycles within the verified mild envelope."""

    def __init__(self, duration=1.0, max_cycles=3, session_duration=30.0,
                 clock=time.monotonic):
        self.duration = min(1.0, max(0.1, float(duration)))
        self.max_cycles = min(3, max(1, int(max_cycles)))
        self.session_duration = min(30.0, max(self.duration,
                                              float(session_duration)))
        self.clock = clock
        self.cycles = 0
        self.active = False
        self.waiting_normal = False
        self.complete = False
        self.cycle_deadline = None
        self.session_deadline = None

    def __call__(self, effect):
        if effect.side != "right":
            return None
        if effect.mode == forceadapt.MODE_NORMAL:
            if not self.active and not self.waiting_normal:
                return None
            self.active = False
            self.waiting_normal = False
            self.cycle_deadline = None
            if self.cycles >= self.max_cycles:
                self.complete = True
            return forceadapt.normal("right")
        if (self.complete or self.waiting_normal
                or effect.mode not in (forceadapt.MODE_RESISTANCE,
                                       forceadapt.MODE_RATTLE)):
            return None
        now = self.clock()
        if self.session_deadline is not None and now >= self.session_deadline:
            return None
        if not self.active:
            if self.cycles >= self.max_cycles:
                self.complete = True
                return None
            self.cycles += 1
            self.active = True
            self.cycle_deadline = now + self.duration
            if self.session_deadline is None:
                self.session_deadline = now + self.session_duration
        if effect.mode == forceadapt.MODE_RATTLE:
            # The exact mild resistance is physically verified.  The game's
            # early rattle event is used only as timing; no rattle mode or
            # unverified rattle parameters reach the APEX 4.
            start, strength = 60, 40
        else:
            start = max(60, min(255, int(effect.params[0])))
            strength = max(1, min(40, int(effect.params[1])))
        return forceadapt.resistance("right", start, strength)

    def expire(self, manager):
        if self.complete:
            return None
        now = self.clock()
        session_due = (self.session_deadline is not None
                       and now >= self.session_deadline)
        cycle_due = (self.active and self.cycle_deadline is not None
                     and now >= self.cycle_deadline)
        if not session_due and not cycle_due:
            return None
        self.active = False
        self.waiting_normal = not session_due and self.cycles < self.max_cycles
        self.complete = session_due or self.cycles >= self.max_cycles
        self.cycle_deadline = None
        return manager.clear_all("bounded dynamic safety timeout", force=True)

    def abort(self):
        self.active = False
        self.waiting_normal = False
        self.complete = True
        self.cycle_deadline = None


class BoundedNativeGate:
    """Allow a few R2 semantic sequences within fixed mode-specific caps."""

    def __init__(self, duration=1.0, max_cycles=1, session_duration=30.0,
                 clock=time.monotonic):
        self.duration = min(4.0, max(0.1, float(duration)))
        self.max_cycles = min(3, max(1, int(max_cycles)))
        self.session_duration = min(30.0, max(self.duration,
                                              float(session_duration)))
        self.clock = clock
        self.cycles = 0
        self.active = False
        self.waiting_normal = False
        self.complete = False
        self.cycle_deadline = None
        self.session_deadline = None

    def __call__(self, effect):
        if effect.side != "right":
            return None
        if effect.mode == forceadapt.MODE_NORMAL:
            if not self.active and not self.waiting_normal:
                return None
            self.active = False
            self.waiting_normal = False
            self.cycle_deadline = None
            if self.cycles >= self.max_cycles:
                self.complete = True
            return forceadapt.normal("right")
        if (self.complete or self.waiting_normal
                or effect.mode not in (forceadapt.MODE_RATTLE,
                                       forceadapt.MODE_RESISTANCE)):
            return None
        now = self.clock()
        if self.session_deadline is not None and now >= self.session_deadline:
            return None
        if not self.active:
            if self.cycles >= self.max_cycles:
                self.complete = True
                return None
            self.cycles += 1
            self.active = True
            self.cycle_deadline = now + self.duration
            if self.session_deadline is None:
                self.session_deadline = now + self.session_duration
        if effect.mode == forceadapt.MODE_RATTLE:
            start, pressure, strength, frequency, _match = effect.params
            return forceadapt.rattle(
                "right", min(60, start), min(1, pressure),
                min(32, strength), min(21, frequency))
        start, strength = effect.params[:2]
        return forceadapt.resistance(
            "right", min(60, start), min(40, strength))

    def expire(self, manager):
        if self.complete:
            return None
        now = self.clock()
        session_due = (self.session_deadline is not None
                       and now >= self.session_deadline)
        cycle_due = (self.active and self.cycle_deadline is not None
                     and now >= self.cycle_deadline)
        if not session_due and not cycle_due:
            return None
        self.active = False
        self.waiting_normal = not session_due and self.cycles < self.max_cycles
        self.complete = session_due or self.cycles >= self.max_cycles
        self.cycle_deadline = None
        return manager.clear_all(
            "bounded native candidate safety timeout", force=True)

    def abort(self):
        self.active = False
        self.waiting_normal = False
        self.complete = True
        self.cycle_deadline = None


class Ow2SafeGate:
    """Continuous R2 cycles for the accepted OW2 rattle/resistance sequence."""

    def __init__(self, duration=4.0, clock=time.monotonic):
        self.duration = min(4.0, max(0.1, float(duration)))
        self.clock = clock
        self.active = False
        self.waiting_normal = False
        self.complete = False
        self.phase = "idle"
        self.deadline = None

    def __call__(self, effect):
        if self.complete or effect.side != "right":
            return None
        if effect.mode == forceadapt.MODE_NORMAL:
            if not self.active and not self.waiting_normal:
                return None
            self.active = False
            self.waiting_normal = False
            self.phase = "idle"
            self.deadline = None
            return forceadapt.normal("right")
        if self.waiting_normal:
            return None
        if not self.active:
            if effect.mode != forceadapt.MODE_RATTLE:
                return None
            self.active = True
            self.phase = "rattle"
            self.deadline = self.clock() + self.duration
        if effect.mode == forceadapt.MODE_RATTLE:
            if self.phase != "rattle":
                return None
            start, pressure, strength, frequency, _match = effect.params
            return forceadapt.rattle(
                "right", min(60, start), min(1, pressure),
                min(32, strength), min(21, frequency))
        if effect.mode == forceadapt.MODE_RESISTANCE:
            if self.phase not in ("rattle", "resistance"):
                return None
            self.phase = "resistance"
            start, strength = effect.params[:2]
            return forceadapt.resistance(
                "right", min(60, start), min(40, strength))
        return None

    def expire(self, manager):
        if (self.complete or not self.active or self.deadline is None
                or self.clock() < self.deadline):
            return None
        self.active = False
        self.waiting_normal = True
        self.phase = "timeout"
        self.deadline = None
        return manager.clear_all("OW2-safe cycle timeout", force=True)

    def abort(self):
        self.active = False
        self.waiting_normal = False
        self.complete = True
        self.phase = "aborted"
        self.deadline = None

    def reset_lifecycle(self):
        """Start fresh after the virtual HID consumer closes and reopens."""
        self.active = False
        self.waiting_normal = False
        self.complete = False
        self.phase = "idle"
        self.deadline = None


class GenericSafeGate:
    """Independent L2/R2 deadlines with Off-only rearming after timeout."""

    MAX_MODE_SECONDS = {
        forceadapt.MODE_RESISTANCE: 15.0,
        forceadapt.MODE_RATTLE: 4.0,
        forceadapt.MODE_BREAKPOINT: 4.0,
    }

    def __init__(self, clock=time.monotonic, mode_seconds=None):
        self.clock = clock
        requested = mode_seconds or {}
        self.mode_seconds = {
            mode: min(limit, max(0.1, float(requested.get(mode, limit))))
            for mode, limit in self.MAX_MODE_SECONDS.items()
        }
        self.deadline = {"left": None, "right": None}
        self.waiting_off = {"left": False, "right": False}

    def __call__(self, effect):
        side = effect.side
        if effect.mode == forceadapt.MODE_NORMAL:
            if self.deadline[side] is None and not self.waiting_off[side]:
                return None
            self.deadline[side] = None
            self.waiting_off[side] = False
            return effect
        if self.waiting_off[side] or effect.mode not in self.mode_seconds:
            return None
        now = self.clock()
        proposed = now + self.mode_seconds[effect.mode]
        if self.deadline[side] is None:
            self.deadline[side] = proposed
        else:
            self.deadline[side] = min(self.deadline[side], proposed)
        if now >= self.deadline[side]:
            return None
        return effect

    def expire(self, manager):
        now = self.clock()
        due = [side for side in ("left", "right")
               if self.deadline[side] is not None
               and now >= self.deadline[side]]
        if not due:
            return None
        ok = True
        for side in due:
            self.deadline[side] = None
            self.waiting_off[side] = True
            if not manager.clear_side(side, "generic-safe timeout", force=True):
                ok = False
        if not ok:
            # The relay retries a bilateral Normal and may close the vendor
            # transport. Do not let the other side continue from stale state.
            self.abort()
        return ok

    def abort(self):
        for side in ("left", "right"):
            self.deadline[side] = None
            self.waiting_off[side] = True

    def reset_lifecycle(self):
        for side in ("left", "right"):
            self.deadline[side] = None
            self.waiting_off[side] = False


class TriggerStateManager:
    def __init__(self, transport=None, enabled=True, dry_run=False, debug=False,
                 reset_timeout=5.0, queue_pending=False,
                 clock=time.monotonic, logger=print, effect_filter=None,
                 pending_ttl=2.0, comparison_translator=None,
                 translator=trigger_translation.translate):
        self.transport = transport
        self.enabled = bool(enabled)
        self.dry_run = bool(dry_run)
        self.debug = bool(debug or dry_run)
        self.reset_timeout = max(0.0, float(reset_timeout))
        self.queue_pending = bool(queue_pending)
        self.pending_ttl = max(0.0, float(pending_ttl))
        self.clock = clock
        self.logger = logger
        self.effect_filter = effect_filter
        self.translator = translator
        self.comparison_translator = comparison_translator
        self.comparison_last = {"left": None, "right": None}
        self.last = {"left": None, "right": None}
        self.pending = {"left": None, "right": None}
        self.last_effect_at = {"left": None, "right": None}
        self.pending_at = {"left": None, "right": None}
        self.last_report_at = None

    def begin_connection(self):
        """Forget every old-pad state before a new identity is accepted."""
        self.transport = None
        self.last = {"left": None, "right": None}
        self.pending = {"left": None, "right": None}
        self.last_effect_at = {"left": None, "right": None}
        self.pending_at = {"left": None, "right": None}
        self.last_report_at = None
        self.comparison_last = {"left": None, "right": None}

    def note_output(self):
        """Record host activity for diagnostics, never for effect freshness."""
        self.last_report_at = self.clock()

    def attach(self, transport):
        """Attach a newly verified controller and clear inherited live state."""
        self.transport = transport
        self.last = {"left": None, "right": None}
        now = self.clock()
        pending = {
            side: effect if (effect is not None
                             and self.pending_at[side] is not None
                             and self.pending_ttl
                             and now - self.pending_at[side] <= self.pending_ttl)
            else None
            for side, effect in self.pending.items()
        }
        cleared = self.clear_all("controller connected", force=True)
        if not cleared:
            abort = getattr(self.effect_filter, "abort", None)
            if abort is not None:
                abort()
            return False
        # Only the continuous accepted profile opts into reconnect recovery.
        # Bounded diagnostic gates intentionally remain aborted after detach.
        reset = getattr(self.effect_filter, "reset_lifecycle", None)
        if reset is not None:
            reset()
        for side in ("left", "right"):
            effect = pending[side]
            if effect is not None and self._send(effect):
                self.last[side] = effect
                self.last_effect_at[side] = now
        return cleared

    def _send(self, effect, prefix=None):
        packet = forceadapt.build_packet(effect)
        label = SIDE_LABELS[effect.side]
        if self.dry_run:
            self.logger("DRY-RUN APEX4 %s: mode=%d params=%s packet=%s"
                        % (label, effect.mode, effect.params, packet.hex(" ")))
            return True
        if self.transport is None:
            if self.debug:
                self.logger("APEX4 %s: not sent (no verified transport)" % label)
            return False
        self.transport.write_effect(effect)
        if self.debug:
            self.logger("APEX4 %s: mode=%d params=%s packet=%s%s"
                        % (label, effect.mode, effect.params, packet.hex(" "),
                           "" if prefix is None else " " + prefix))
        return True

    def handle(self, raw_effect, left_motor=0, context=None):
        if not self.enabled:
            return False
        self.note_output()
        # A safety filter must not consume its one allowed effect before the
        # same-fd identity gate has attached a verified physical transport.
        if (self.effect_filter is not None and self.transport is None
                and not self.dry_run):
            return False
        normalized = trigger_translation.parse(raw_effect)
        if normalized is None:
            if self.debug:
                self.logger("DS5 trigger: malformed effect ignored")
            return False
        mapped = self.translator(raw_effect, left_motor)
        label = SIDE_LABELS[normalized.side]
        if self.comparison_translator is not None:
            compatibility = trigger_translation.translate(raw_effect, left_motor)
            candidate = self.comparison_translator(raw_effect, left_motor)
            comparison_key = (compatibility, candidate)
            if comparison_key != self.comparison_last[normalized.side]:
                self.comparison_last[normalized.side] = comparison_key
                compat = ("none" if compatibility is None else
                          "mode=%d params=%s"
                          % (compatibility.mode, compatibility.params))
                semantic = ("none" if candidate is None else
                            "mode=%d params=%s"
                            % (candidate.mode, candidate.params))
                suffix = ""
                if context:
                    suffix = (" t=%.6f physical_l2=%d physical_r2=%d"
                              % (context.get("t", self.clock()),
                                 context.get("physical_l2", -1),
                                 context.get("physical_r2", -1)))
                self.logger("COMPARE %s: compat=%s semantic=%s%s"
                            % (label, compat, semantic, suffix))
        if mapped is None:
            if self.debug:
                self.logger("DS5 %s: %s -> no safe ForceAdapt mapping"
                            % (label, normalized.describe()))
            return False
        if self.effect_filter is not None:
            mapped = self.effect_filter(mapped)
            if mapped is None:
                return False
        now = self.clock()
        self.last_effect_at[mapped.side] = now
        if (mapped == self.last[mapped.side]
                or mapped == self.pending[mapped.side]):
            return False
        if self.debug:
            self.logger("DS5 %s: %s" % (label, normalized.describe()))
        if self._send(mapped):
            self.last[mapped.side] = mapped
            return True
        if self.queue_pending and self.transport is None:
            self.pending[mapped.side] = mapped
            self.pending_at[mapped.side] = now
        elif self.debug and self.transport is None:
            # Debug-only mode is read-only but should still avoid repeating the
            # same decoded decision for every identical game output report.
            self.last[mapped.side] = mapped
        return False

    def clear_side(self, side, reason="reset", force=False):
        """Clear one trigger without resetting the other side's live effect."""
        if side not in SIDE_LABELS:
            raise ValueError("trigger side must be left or right")
        self.pending[side] = None
        self.pending_at[side] = None
        effect = forceadapt.normal(side)
        if not force and self.last[side] == effect:
            return True
        try:
            sent = self._send(effect, "reason=%s" % reason)
        except OSError as exc:
            self.logger("APEX4 %s clear failed: %s"
                        % (SIDE_LABELS[side], exc))
            return False
        if sent:
            self.last[side] = effect
            self.last_effect_at[side] = None
        return sent

    def clear_all(self, reason="reset", force=False):
        # A lifecycle reset invalidates an effect seen while identity probing;
        # it must never be replayed after the game has already closed.
        self.pending = {"left": None, "right": None}
        self.pending_at = {"left": None, "right": None}
        attempted = False
        ok = True
        for side in ("left", "right"):
            effect = forceadapt.normal(side)
            if not force and self.last[side] == effect:
                continue
            attempted = True
            try:
                sent = self._send(effect, "reason=%s" % reason)
                ok = ok and sent
                if sent:
                    self.last[side] = effect
            except OSError as exc:
                ok = False
                self.logger("APEX4 %s clear failed: %s"
                            % (SIDE_LABELS[side], exc))
        return attempted and ok

    def reset_lifecycle(self, reason="lifecycle reset"):
        """Clear hardware and reset only filters designed for HID reopen."""
        cleared = self.clear_all(reason, force=True)
        hook = "reset_lifecycle" if cleared else "abort"
        action = getattr(self.effect_filter, hook, None)
        if action is not None:
            action()
        self.comparison_last = {"left": None, "right": None}
        return cleared

    def expire(self):
        if not self.enabled:
            return None
        now = self.clock()
        pending_expired = False
        if self.pending_ttl:
            for side, effect in tuple(self.pending.items()):
                stamp = self.pending_at[side]
                if (effect is not None and stamp is not None
                        and now - stamp >= self.pending_ttl):
                    self.pending[side] = None
                    self.pending_at[side] = None
                    pending_expired = True
        stale_active = False
        if self.reset_timeout:
            for side in ("left", "right"):
                effects = (self.last[side], self.pending[side])
                if not any(effect is not None
                           and effect.mode != forceadapt.MODE_NORMAL
                           for effect in effects):
                    continue
                stamp = self.last_effect_at[side]
                if stamp is not None and now - stamp >= self.reset_timeout:
                    stale_active = True
                    break
        if not pending_expired and not stale_active:
            return None
        return self.clear_all("DualSense output timeout", force=True)

    def detach(self, reason="disconnect"):
        self.clear_all(reason, force=True)
        abort = getattr(self.effect_filter, "abort", None)
        if abort is not None:
            abort()
        self.transport = None
        self.last = {"left": None, "right": None}
        self.pending = {"left": None, "right": None}
        self.last_effect_at = {"left": None, "right": None}
        self.pending_at = {"left": None, "right": None}
        self.last_report_at = None
        self.comparison_last = {"left": None, "right": None}

    def disable(self):
        self.clear_all("feature disabled", force=True)
        abort = getattr(self.effect_filter, "abort", None)
        if abort is not None:
            abort()
        self.enabled = False
