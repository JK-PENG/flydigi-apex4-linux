# SPDX-License-Identifier: MIT
"""Non-blocking identity-probe timing for the ForceAdapt safety gate."""


NO_REPLY = "ForceAdapt refused: no valid command 0xEC identity reply"


class IdentityProbe:
    """Schedule bounded EC probes and quiet retries for one HID generation.

    Some APEX 4 reconnects enumerate before their vendor command channel will
    answer.  A failed two-second probe must therefore remain fail-closed while
    retrying later; it must not permanently disable ForceAdapt for that live
    connection.  Validation failures are terminal because retrying cannot make
    an unsupported identity safe.
    """

    def __init__(self, generation, now, timeout=2.0, resend_interval=0.15,
                 retry_initial=5.0, retry_max=30.0):
        self.generation = generation
        self.timeout = float(timeout)
        self.resend_interval = float(resend_interval)
        self.retry_delay = float(retry_initial)
        self.retry_max = float(retry_max)
        self.deadline = float(now) + self.timeout
        self.next_request = float(now)
        self.retry_at = None
        self.last_error = None
        self.terminal = False

    def request_due(self, now):
        return (not self.terminal and self.deadline is not None
                and now < self.deadline and now >= self.next_request)

    def mark_requested(self, now):
        self.next_request = float(now) + self.resend_interval

    def mark_rejected(self, error):
        """Remember a parsed-but-unsafe identity until this attempt ends."""
        self.last_error = str(error)

    def timeout_result(self, now):
        """Return ``(message, retry_seconds)`` once an attempt times out."""
        if self.deadline is None or now < self.deadline:
            return None
        self.deadline = None
        if self.last_error is not None:
            self.terminal = True
            self.retry_at = None
            return self.last_error, None
        delay = self.retry_delay
        self.retry_at = float(now) + delay
        self.retry_delay = min(delay * 2.0, self.retry_max)
        return NO_REPLY, delay

    def resume_if_due(self, now):
        """Start the next bounded attempt after its quiet backoff."""
        if (self.terminal or self.deadline is not None
                or self.retry_at is None or now < self.retry_at):
            return False
        self.deadline = float(now) + self.timeout
        self.next_request = float(now)
        self.retry_at = None
        self.last_error = None
        return True
