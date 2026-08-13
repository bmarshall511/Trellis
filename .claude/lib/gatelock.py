"""A lock held while the quality gates run.

Gates start servers, bind ports and name containers. Two runs at once collide on all three, and the
collision does not announce itself as contention — it surfaces as ERR_CONNECTION_REFUSED, which reads
exactly like a broken product. Someone diagnosed it only because the tests that needed no server were
the ones that passed.

That is the worst shape a bug can take: the symptom points at the wrong thing. So gates are serialised
rather than left to collide.

It happens in practice because the Stop hook and the delivery script both run the gates, and the Stop
hook can fire while delivery is mid-flight.

Cooperative, not enforced — a lock file plus liveness, which is enough for processes that want to
cooperate and is not trying to defend against ones that don't.
"""
import errno
import os
import time

__all__ = ["gate_lock", "GateBusy"]

LOCK_NAME = ".claude/.gates.lock"
STALE_AFTER = 3600  # an hour: longer than any honest gate run, shorter than a forgotten lock


class GateBusy(Exception):
    """Raised when another process holds the lock and the wait timed out."""


def _alive(pid):
    try:
        os.kill(pid, 0)
    except OSError as exc:
        return exc.errno == errno.EPERM  # exists but is not ours
    except Exception:
        return False
    return True


def _read(path):
    try:
        with open(path) as handle:
            pid, stamp, owner = handle.read().split("\n")[:3]
            return int(pid), float(stamp), owner
    except Exception:
        return None, None, None


def _stale(path):
    """A lock is stale if its owner is gone, or if it is older than any honest gate run.

    Both matter. A killed process leaves a lock nothing will release, and without the age check a
    machine that reused the pid would keep the lock alive forever.
    """
    pid, stamp, _ = _read(path)
    if pid is None:
        return True
    if not _alive(pid):
        return True
    return stamp is not None and (time.time() - stamp) > STALE_AFTER


class gate_lock:  # noqa: N801 — used as a context manager, reads as one
    """Serialises gate runs.

        with gate_lock(root, owner="verify-gate", timeout=900):
            run_the_gates()

    timeout=0 raises GateBusy immediately rather than waiting, for callers that would rather report
    contention than queue behind it.
    """

    def __init__(self, root, owner="gates", timeout=900, poll=2):
        self.path = os.path.join(root, LOCK_NAME)
        self.owner = owner
        self.timeout = timeout
        self.poll = poll
        self.held = False

    def _acquire_once(self):
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            if _stale(self.path):
                try:
                    os.unlink(self.path)
                except OSError:
                    pass
                return False  # try again next poll rather than racing to recreate it
            return False
        except OSError:
            return False
        with os.fdopen(fd, "w") as handle:
            handle.write("%d\n%f\n%s\n" % (os.getpid(), time.time(), self.owner))
        return True

    def __enter__(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        deadline = time.time() + self.timeout
        while True:
            if self._acquire_once():
                self.held = True
                return self
            if time.time() >= deadline:
                _, _, owner = _read(self.path)
                raise GateBusy(
                    "another process is running the gates%s. Gates bind ports and name containers, so "
                    "running two at once produces connection errors that look like product bugs."
                    % (" (%s)" % owner if owner else ""))
            time.sleep(self.poll)

    def __exit__(self, *_):
        if self.held:
            try:
                os.unlink(self.path)
            except OSError:
                pass
            self.held = False
        return False
