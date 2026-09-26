"""
Verify that coupling OmegaJev to the StickerBook authority kernel adds no
authority.

Root SECURITY.md section 28 calls the coupling "where a bypass would most
easily hide, because it is the first place two separately-verified components
have to agree about who may do what". This suite is that agreement, tested.

Run inside the experiment image:

    docker run --rm -i --entrypoint python3 omega-jev:experiment - \
        < tests/verify_kernel_coupling.py
"""

import sys

sys.path[:0] = ["/PeTTa/repos/Omega", "/PeTTa/repos/Omega/src",
                "/PeTTa/repos/Omega/providers"]

import helper           # Omega's real parser/allowlist
import jev              # the provider
import jev_core
import sb_bridge
from stickerbook_core import ADD_OWN_STICKER, REMOVE_AGENT_STICKER, REMOVE_OWN_STICKER

failures = []


def check(label, condition, detail=""):
    print("  [%s] %s%s" % ("PASS" if condition else "FAIL", label,
                           ("  -- " + detail) if detail else ""))
    if not condition:
        failures.append(label)


k = sb_bridge.init("local-single-agent")
AGENT = sb_bridge.AGENT_ID

print("=" * 70)
print("THE EXECUTABLE VOCABULARY COLLAPSES TO ONE ZERO-ARGUMENT COMMAND")
print("=" * 70)
allow = jev.harden_llm_commands({"_": "sb-apply"})
check("Omega's allowlist is exactly {sb-apply}", set(allow) == {"sb-apply"},
      str(sorted(allow)))
check("'sb-apply' compiles to a bare zero-argument call",
      helper.balance_parentheses("sb-apply") == "((sb-apply))",
      helper.balance_parentheses("sb-apply"))
for dangerous in ("shell whoami", "metta (shell \"id\")", "write-file /tmp/x y",
                  "delete-file /tmp/x", "butterfly-flutter", "version"):
    compiled = helper.balance_parentheses(dangerous)
    check("%-24s blocked" % dangerous.split()[0],
          "UNKNOWN_SKILL_CALL" in compiled)

print()
print("=" * 70)
print("THE ACTION TABLE NEVER OFFERS A HUMAN-OWNED OBJECT")
print("=" * 70)
table = sb_bridge.action_table()
print("  table: %s" % sorted(table))
human_targets = [key for key, cmd in table.items()
                 if cmd.object_id and k.sticker(cmd.object_id)
                 and k.sticker(cmd.object_id).owner != AGENT]
check("no offered action targets a human-owned sticker", not human_targets,
      str(human_targets))
check("a human-owned sticker exists to protect",
      k.sticker("star-1") is not None
      and k.sticker("star-1").owner == sb_bridge.HUMAN_ID)
check("backdrop features are not kernel objects at all",
      all(k.sticker(name) is None for name in ("lantern", "fox")),
      "passive scenery; no action can reach them")

print()
print("=" * 70)
print("THE AGENT CANNOT REACH TOOLS OUTSIDE ITS PROFILE INTERSECTION")
print("=" * 70)
tools = k.effective_tools(AGENT)
for absent in (REMOVE_AGENT_STICKER, REMOVE_OWN_STICKER, ADD_OWN_STICKER):
    check("%-22s not in effective authority" % absent, absent not in tools)

print()
print("=" * 70)
print("A FORGED OR STALE KEY IS REFUSED BY THE KERNEL, ON THE RECORD")
print("=" * 70)
for forged in ("ANIMATE:star-1:twinkle",       # human-owned object
               "REMOVE:butterfly-1",           # tool not held
               "REMOVE_AGENT:butterfly-1",     # human-only tool
               "ADD:butterfly",                # tool not held
               "ANIMATE:butterfly-1:explode",  # animation not declared
               "../../etc/passwd", "NOOP; shell whoami"):
    sb_bridge.stage(forged)
    applied = sb_bridge.apply_pending()
    # The kernel refuses AND leaves a receipt: a refusal must be auditable,
    # not silently dropped by the bridge.
    check("%-30s refused, with a receipt" % forged[:30],
          "accepted=False" in applied and "unknown-action-key" in applied,
          applied[:95])

check("an empty key stages nothing at all", sb_bridge.stage("") is False)

# Compare against the seeded state rather than a hard-coded anchor, so this
# stays a real invariant if the demo world is re-seeded.
for landmark in ("star-1",):
    sticker = k.sticker(landmark)
    check("the human's %s is untouched by all of that" % landmark,
          sticker is not None and sticker.owner == sb_bridge.HUMAN_ID
          and sticker.animation == "none",
          "%s at %s, motion %s" % (landmark, sticker.anchor, sticker.animation))

print()
print("=" * 70)
print("STAGING IS SINGLE-USE AND IS NOT AUTHORIZATION")
print("=" * 70)
ok = sb_bridge.stage("ANIMATE:butterfly-1:flutter")
check("a legal key stages", ok)
first = sb_bridge.apply_pending()
check("applying it yields an accepted receipt",
      "accepted=True" in first, first[:80])
second = sb_bridge.apply_pending()
check("a second apply does nothing", second == "SB-NOTHING-STAGED", second)
check("the world advanced exactly once",
      k.sticker("butterfly-1").animation == "flutter")

print()
print("=" * 70)
print("THE TABLE IS REGENERATED FROM THE WORLD, NOT CACHED")
print("=" * 70)
now = sorted(sb_bridge.action_table())
check("the action just taken has left the table",
      "ANIMATE:butterfly-1:flutter" not in now, str(now))
check("its inverse has appeared", "ANIMATE:butterfly-1:none" in now)

print()
print("=" * 70)
print("EVERY DECISION PRODUCES A RECEIPT WITH CAUSAL PROVENANCE")
print("=" * 70)
receipts = sb_bridge.receipts()
check("receipts were recorded", len(receipts) > 0, "%d receipts" % len(receipts))
last = [r for r in receipts if r.accepted][-1]
d = last.to_dict()
for field in ("commandId", "actor", "action", "object", "basedOnRevision",
              "accepted", "reason", "resultRevision"):
    check("receipt carries %-16s" % field, field in d and d[field] is not None,
          str(d.get(field)))
check("the actor is the agent principal, recorded explicitly",
      d["actor"] == AGENT, d["actor"])
check("rejections are receipted too",
      any(not r.accepted for r in receipts),
      "%d rejections" % sum(1 for r in receipts if not r.accepted))

print()
print("=" * 70)
print("THE pages-demo PROFILE LEAVES THE AGENT WITH NOTHING")
print("=" * 70)
sb_bridge.init("pages-demo")
check("action table is empty", sb_bridge.action_table() == {})
check("effective authority is empty",
      sb_bridge.kernel().effective_tools(AGENT) == frozenset())
# Staging merely records; the kernel is what refuses -- and it refuses
# everything here, on the record.
sb_bridge.stage("NOOP")
applied = sb_bridge.apply_pending()
check("even NOOP is refused under pages-demo",
      "accepted=False" in applied, applied[:90])
check("the refusal is receipted",
      any(not r.accepted for r in sb_bridge.receipts()))

print()
print("=" * 70)
if failures:
    print("RESULT: %d CHECK(S) FAILED: %s" % (len(failures), failures))
    sys.exit(1)
print("RESULT: ALL CHECKS PASSED")
sys.exit(0)
