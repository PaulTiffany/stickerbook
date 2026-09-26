"""
Empirically verify the runtime filesystem boundary, as the agent user.

Run it with:
    docker run --rm -i --user 65534 -w /PeTTa --entrypoint python3 \
        omega-jev:experiment - < this_file

Checks that, after Omega's own Landlock policy is applied, the running agent
can write ONLY to its memory directory and /tmp, and cannot modify its own
source code or read sensitive files.
"""

import os
import sys

sys.path[:0] = ["/PeTTa/repos/Omega", "/PeTTa/repos/Omega/src",
                "/PeTTa/repos/Omega/profile"]

failures = []


def check(label, condition, detail=""):
    print("  [%s] %s%s" % ("PASS" if condition else "FAIL", label,
                           ("  -- " + detail) if detail else ""))
    if not condition:
        failures.append(label)


def can_write(path):
    """Attempt a real write. Returns (succeeded, reason)."""
    try:
        with open(path, "a"):
            pass
        return True, "opened for append"
    except Exception as exc:
        return False, type(exc).__name__ + ": " + str(exc)


def can_read(path):
    try:
        with open(path, "rb") as handle:
            handle.read(1)
        return True, "read ok"
    except Exception as exc:
        return False, type(exc).__name__ + ": " + str(exc)


print("running as uid=%d gid=%d" % (os.getuid(), os.getgid()))
print()
print("=" * 70)
print("BEFORE Landlock: POSIX permissions alone")
print("=" * 70)
ok, why = can_write("/PeTTa/repos/Omega/providers/jev.py")
check("cannot modify own source (POSIX)", not ok, why)
ok, why = can_write("/PeTTa/repos/Omega/memory/boundary_probe.txt")
check("can write to memory dir", ok, why)

# /run/lock is world-writable (1777) but is NOT in policy.yaml. It is the one
# place where POSIX permits a write and only Landlock can deny it, so it
# isolates Landlock's independent contribution from file ownership.
ok, why = can_write("/run/lock/landlock_probe.txt")
check("CAN write /run/lock before Landlock (POSIX allows it)", ok, why)

print()
print("=" * 70)
print("APPLYING Omega's Landlock policy")
print("=" * 70)
import policy  # noqa: E402

policy.apply_security_policy("./repos/Omega/profile/policy.yaml")
print("  policy applied")

print()
print("=" * 70)
print("AFTER Landlock: enforcement")
print("=" * 70)

ok, why = can_write("/PeTTa/repos/Omega/providers/jev.py")
check("still cannot modify own source", not ok, why)

ok, why = can_write("/PeTTa/repos/Omega/profile/policy.yaml")
check("cannot rewrite the policy itself", not ok, why)

ok, why = can_write("/tmp/probe.txt")
check("CAN write /tmp (allowed by policy)", ok, why)

ok, why = can_write("/PeTTa/repos/Omega/memory/boundary_probe.txt")
check("CAN write memory dir (allowed by policy)", ok, why)

ok, why = can_write("/etc/passwd")
check("cannot write /etc/passwd", not ok, why)

ok, why = can_read("/etc/shadow")
check("cannot read /etc/shadow", not ok, why)

ok, why = can_write("/opt/nginx/nginx.conf")
check("cannot read/write the credential-bearing nginx config", not ok, why)

ok, why = can_read("/opt/nginx/nginx.conf")
check("cannot read generated nginx.conf (holds the API key)", not ok, why)

# The isolating check: POSIX allowed this write moments ago. If it is denied
# now, the denial can only have come from Landlock.
ok, why = can_write("/run/lock/landlock_probe2.txt")
check("LANDLOCK ALONE now denies /run/lock", not ok, why)

print()
print("=" * 70)
if failures:
    print("RESULT: %d CHECK(S) FAILED: %s" % (len(failures), failures))
    sys.exit(1)
print("RESULT: ALL CHECKS PASSED")
sys.exit(0)
