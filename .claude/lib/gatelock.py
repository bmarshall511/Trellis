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

The lock belongs to whichever process actually *runs* the gates, and is held for exactly as long as
they run. A caller that merely invokes something that runs the gates must not take a second lock at
its own layer: the first version of this did, from a throwaway `python3 -c` that wrote its pid and
exited, so the lock was stale from birth and any other runner reclaimed it in two seconds. Hook
against hook was serialised; delivery against hook, the pairing it was written for, was not.

The obvious repair — hold it in a process that outlives the gates — walks into the opposite failure,
because the thing delivery invokes is the Stop hook, which locks correctly on its own. The parent
would be waited on by its own child for the full timeout and then told the gates were red. So a
nested acquire is a no-op rather than a deadlock, tracked through the environment: see HELD_ENV.
"""
import contextlib
import errno
import os
import time

__all__ = ["GateBusy", "gate_lock"]

LOCK_NAME = ".claude/.gates.lock"
STALE_AFTER = 3600  # an hour: longer than any honest gate run, shorter than a forgotten lock

# Set to the holder's pid on acquire, so child processes can tell "someone else is running the gates"
# from "the gates I am part of are already locked". Children inherit the environment; unrelated
# processes do not, which is exactly the distinction needed.
HELD_ENV = "TRELLIS_GATE_LOCK"


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


def _held_by_us(path):
    """True if the lock is already held by this process or one that spawned it.

    Without this, a caller that locks and then invokes something that locks too — which is what the
    Stop hook is — waits on itself for the whole timeout and reports the gates as red.
    """
    inherited = os.environ.get(HELD_ENV)
    if not inherited:
        return False
    try:
        holder = int(inherited)
    except ValueError:
        return False
    pid, _, _ = _read(path)
    return pid is not None and pid == holder and _alive(holder)


class gate_lock:
    """Serialises gate runs.

        with gate_lock(root, owner="verify-gate", timeout=900):
            run_the_gates()

    Use it as a context manager, in the process that runs the gates. Calling `__enter__()` from a
    process that then exits leaves a lock that is stale the instant it is written, which reads as a
    lock and protects nothing.

    Reentrant: acquiring inside a process that already holds it succeeds immediately and releases
    nothing, so the outermost holder stays in charge.

    timeout=0 raises GateBusy immediately rather than waiting, for callers that would rather report
    contention than queue behind it.
    """

    def __init__(self, root, owner="gates", timeout=900, poll=2):
        self.path = os.path.join(root, LOCK_NAME)
        self.owner = owner
        self.timeout = timeout
        self.poll = poll
        self.held = False
        self.reentrant = False

    def _acquire_once(self):
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            if _stale(self.path):
                with contextlib.suppress(OSError):
                    os.unlink(self.path)
                return False  # try again next poll rather than racing to recreate it
            return False
        except OSError:
            return False
        with os.fdopen(fd, "w") as handle:
            handle.write("%d\n%f\n%s\n" % (os.getpid(), time.time(), self.owner))
        os.environ[HELD_ENV] = str(os.getpid())  # inherited by anything we go on to run
        return True

    def __enter__(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if _held_by_us(self.path):
            self.reentrant = True
            return self
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
            with contextlib.suppress(OSError):
                os.unlink(self.path)
            os.environ.pop(HELD_ENV, None)
            self.held = False
        return False  # a reentrant acquire releases nothing: the outermost holder still owns it
