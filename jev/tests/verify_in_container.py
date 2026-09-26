"""
In-container verification of the authority boundary.

Unlike tests/test_jev_core.py (which tests our adapter in isolation), this runs
inside the real experiment image against Omega's REAL helper.py, and proves
that what actually reaches Omega's parser is restricted.

Run it with:
    docker run --rm -i --entrypoint python3 omega-jev:experiment - < this_file

Exit code 0 means every check passed.
"""

import sys

sys.path[:0] = [
    "/PeTTa/repos/Omega",
    "/PeTTa/repos/Omega/src",
    "/PeTTa/repos/Omega/providers",
]

import helper  # Omega's real parser/allowlist module

failures = []


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print("  [%s] %s%s" % (status, label, ("  -- " + detail) if detail else ""))
    if not condition:
        failures.append(label)


DANGEROUS = {
    "shell": "shell whoami",
    "metta": "metta (shell \"whoami\")",
    "write-file": "write-file /tmp/x.txt hello",
    "write-file-b64": "write-file-b64 /tmp/x.txt aGk=",
    "append-file": "append-file /tmp/x.txt hello",
    "delete-file": "delete-file /tmp/x.txt",
    "read-file": "read-file /etc/passwd",
    "websearch": "websearch secrets",
    "send": "send hello world",
    "remember": "remember something",
    "query": "query something",
    "get-io-policy": "get-io-policy",
    "episodes": "episodes 2026-09-26 18:30:00",
    "pin": "pin some task state",
    "search": "search something",
}

print("=" * 70)
print("BASELINE: Omega's stock allowlist, before Jev hardening")
print("=" * 70)
stock = sorted(helper.LLM_COMMANDS)
print("  stock LLM_COMMANDS (%d): %s" % (len(stock), stock))
check("stock Omega does allow 'shell'", "shell" in helper.LLM_COMMANDS,
      "this is what we are removing")
check("stock Omega does allow 'metta'", "metta" in helper.LLM_COMMANDS)

print()
print("=" * 70)
print("APPLYING JEV HARDENING")
print("=" * 70)
import jev  # noqa: E402  -- importing runs no side effects beyond definitions
import jev_core  # noqa: E402

allowlist = jev.harden_llm_commands()
print("  effective allowlist: %s" % sorted(allowlist))
check("allowlist is exactly {jev-noop, version}",
      set(allowlist) == {"jev-noop", "version"})

print()
print("=" * 70)
print("REQUIREMENTS 5/6/7: dangerous skills cannot reach eval")
print("=" * 70)
for name, line in sorted(DANGEROUS.items()):
    compiled = helper.balance_parentheses(line)
    blocked = "UNKNOWN_SKILL_CALL" in compiled and ("(" + name + " ") not in compiled
    check("%-16s blocked" % name, blocked, compiled[:60])

# Completeness: every stock Omega command except `version` must be blocked,
# so the claim is about the whole upstream surface, not a chosen subset.
missing = (set(stock) - set(DANGEROUS)) - {"version"}
check("every stock command except 'version' is covered above", not missing,
      "uncovered: " + str(sorted(missing)) if missing else "16 stock commands")

print()
print("=" * 70)
print("ACTION SET ISOLATION: an inactive set is not executable")
print("=" * 70)
# The generic set is active, so the Stage 3 butterfly skills -- which DO exist
# as real MeTTa functions in the image -- must not be reachable.
for name in ("butterfly-flutter", "butterfly-rest"):
    compiled = helper.balance_parentheses(name)
    check("%-18s blocked while generic set active" % name,
          "UNKNOWN_SKILL_CALL" in compiled, compiled[:55])

# ...and switching sets swaps which are reachable, in both directions.
butterfly_allow = jev.harden_llm_commands(jev_core.ACTIONS_BUTTERFLY)
check("butterfly set allows exactly its own heads",
      set(butterfly_allow) == {"butterfly-flutter", "butterfly-rest", "jev-noop"},
      str(sorted(butterfly_allow)))
check("'version' blocked while butterfly set active",
      "UNKNOWN_SKILL_CALL" in helper.balance_parentheses("version"))
check("'shell' still blocked under butterfly set",
      "UNKNOWN_SKILL_CALL" in helper.balance_parentheses("shell whoami"))
jev.harden_llm_commands()  # restore the generic set for the checks below

print()
print("=" * 70)
print("ROOT INVARIANT: executing permitted actions cannot expand the")
print("capability set (root SECURITY.md test 6)")
print("=" * 70)
# Omega CAN grow its own vocabulary at runtime: helper.add_llm_command() is
# reachable from add-skill, which is reachable from the `metta` skill. The
# claim is that no action in any Jev table reaches that path.
before = set(helper.LLM_COMMANDS)
sys.path.insert(0, "/PeTTa/repos/Omega/plugins/jevskills")
import butterfly  # noqa: E402  -- the only action body with a side effect

butterfly.flutter()
butterfly.rest()
check("executing every side-effecting action leaves the allowlist unchanged",
      set(helper.LLM_COMMANDS) == before, str(sorted(helper.LLM_COMMANDS)))

# The general escape hatch into add-skill is `metta`; confirm it stays shut.
check("'metta' (the route to add-skill) is not reachable",
      "metta" not in helper.LLM_COMMANDS)

# Every literal in every table is a bare command head with no arguments, so
# there is no argument position in which anything could be smuggled.
all_literals = []
for _name, (_actions, _crit) in jev_core.ACTION_SETS.items():
    all_literals.extend(_actions.values())
check("every action literal is a bare zero-argument command head",
      all(" " not in literal for literal in all_literals),
      str(sorted(set(all_literals))))

print()
print("=" * 70)
print("REQUIREMENT 10: only host literals compile to real commands")
print("=" * 70)
check("'version'  -> ((version))",
      helper.balance_parentheses("version") == "((version))",
      helper.balance_parentheses("version"))
check("'jev-noop' -> ((jev-noop))",
      helper.balance_parentheses("jev-noop") == "((jev-noop))",
      helper.balance_parentheses("jev-noop"))

print()
print("=" * 70)
print("FAIL-CLOSED OUTPUT executes nothing")
print("=" * 70)

empty = helper.balance_parentheses(jev_core.FAIL_CLOSED_OUTPUT)
check("fail-closed output compiles to '()'", empty == "()", repr(empty))
check("'()' contains no command", "(" + "version" not in empty and "shell" not in empty)

print()
print("=" * 70)
print("REMOVED CAPABILITIES ARE PHYSICALLY ABSENT FROM THE IMAGE")
print("=" * 70)
import os  # noqa: E402

for path in ["channels/telegram.py", "channels/slack.py", "channels/irc.py",
             "channels/mattermost.py", "channels/wschat.py",
             "providers/openrouter.py", "providers/openai.py",
             "providers/asione.py", "providers/mockprovider.py"]:
    full = "/PeTTa/repos/Omega/" + path
    check("%-28s deleted" % path, not os.path.exists(full))

print()
print("=" * 70)
print("CREDENTIAL ISOLATION")
print("=" * 70)
check("OPENROUTER_API_KEY absent from this environment",
      "OPENROUTER_API_KEY" not in os.environ,
      "note: run under the real entrypoint this is scrubbed; see run log")

print()
print("=" * 70)
if failures:
    print("RESULT: %d CHECK(S) FAILED: %s" % (len(failures), failures))
    sys.exit(1)
print("RESULT: ALL CHECKS PASSED")
sys.exit(0)
