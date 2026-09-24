# DualSense → APEX 4 translation profiles

This document separates three things that were previously easy to conflate:

- **decoded semantics**: what the DualSense report says;
- **compatibility mapping**: constants transcribed from Flydigi's
  `PS5DataManager.ProcessDataWithResult` through openflydigi;
- **semantic candidate**: a direct mapping from decoded regions, strength and
  frequency onto the APEX 4 vocabulary.

The compatibility mapping remains available for comparison and replay, not for
production writes. The accepted runtime profile is `ow2-safe`: it recognizes
only the captured OW2/Hanzo R2 patterns, uses the semantic mapping with tested
caps, enforces order and a four-second deadline, and requires Off before rearm.
No mapping is accepted solely because a packet can be built or written.

## Generic-safe candidate (not yet the installed default)

`apex4ds5.generic_trigger.GenericSafeTranslator` applies one semantic rule to
both sides, with no game/AppID or complete-report whitelist. It is a pure
decision layer; the relay still needs verified transport and an independent
bounded lifecycle gate. The currently released software modes are Normal (0),
resistance (1), and rattle (2). Mode 3 is an explicit test-only candidate until
both-side physical acceptance. Selecting a mode in a test does not authorize a
live hardware write.

| DualSense source | Generic candidate | Loss / current gate |
|---|---|---|
| Off `0x05` | same-side Normal | exact clear |
| simple/zone feedback `0x01/0x21` | mode 1, decoded start, strength at most 40 | higher resistance clipped; L2 and long-hold acceptance pending |
| simple/zone vibration `0x06/0x26` | mode 2, decoded start, pressure 1, strength at most 32, frequency at most 21 | richer pulse shapes unsupported; L2 acceptance pending |
| simple/zone weapon, bow `0x02/0x25/0x22` | candidate mode 3, start at least 60, travel/strength at most 20 | shifts early breakpoints and loses bow snap; closed pending physical test |
| galloping/machine `0x23/0x27` | no generic write | existing mode-2 approximation is not independently accepted for this semantic class |
| zero-strength/frequency, empty/invalid zone, limited/unknown | no write | existing active effect still cleared by Off or safety deadline |

The captured OW2 `0x26` and `0x21` blocks are regression examples, not the only
accepted input bytes. The generic decision table is not a claim that an Edge
game sends output or that the 15-second resistance candidate is comfortable;
those require later game and holder evidence.
Fixed simple/zone/weapon/unsupported virtual-output vectors are available in
`tools/relay-trigger-test.py` and exercised by `tests/test_adaptive_triggers.py`.

## Evidence boundary

openflydigi documents its mapping as recognition of byte patterns emitted by
particular games, with hand-tuned Flydigi effects. It is valuable compatibility
evidence, not a general conversion formula. See the pinned MIT source in
`THIRD_PARTY_NOTICES.md` and
[`relay.py`](https://github.com/mkaliaha/openflydigi/blob/8477300f1bd0cdd0e4a277a544aa9b151c623e62/flydigi/relay.py#L48-L64).

Older OW2 evidence preserved decoded summaries rather than complete raw
10-byte blocks. The 2026-09-21 synchronized capture now stores representative
complete game reports in `tests/fixtures/ow2-hanzo-2026-09-21.json`. Older
upstream-derived vectors remain labelled reconstructed; only this fixture is
labelled game-captured.

## Main effect table

| DS type | Decoded meaning | Compatibility mapping | Semantic candidate | Status |
|---|---|---|---|---|
| `0x05` | Off | Normal, same side | Normal, same side | exact clear |
| `0x01` | simple resistance | raw start/strength → Race | same | direct fields |
| `0x02` | simple weapon | raw start/travel/strength → breakpoint | same | direct fields |
| `0x06` | simple vibration | raw values → mode 2 | raw start/strength/frequency → mode 2 | needs hardware semantics |
| `0x21` | zone resistance | side- and pattern-specific constants | decoded start zone and maximum decoded strength → Race | exact captured OW2 pattern accepted at strength cap 40; generic compare only |
| `0x25` | weapon/breakpoint | pattern-specific constants | decoded start/end/strength → breakpoint | compare in game |
| `0x26` | zone vibration | start from mask, strength derived from mask byte, frequency raw | decoded start zone, packed strength and frequency → mode 2 | exact captured OW2 pattern accepted at strength 32/frequency 21; generic compare only |
| `0x22/23/27` | bow/gallop/machine | documented approximations | decoded region/intensity approximation | no current OW2 dependency |

APEX mode 2 is the physically observed rattle/recoil behavior despite Flydigi's
crossed enum labels; mode 5 remains unused. Byte clamping proves encodability,
not comfort or semantic fidelity.

## OW2 captured comparison

For the captured full-zone `0x26` vector:

```text
decoded:    start=0 end=9 strength=32 frequency=21
compat:     mode=2 params=(0, 1, 120, 21, 0)
semantic:   mode=2 params=(0, 1, 32, 21, 0)
```

For the captured `0x21` vector:

```text
decoded:    start=0 end=9 strength=96
compat:     mode=1 params=(1, 64, 0, 0, 0)
semantic:   mode=1 params=(0, 96, 0, 0, 0)
```

In three holder-correlated cycles, `0x26` arrived at physical R2 11..14,
`0x21` followed 0.719..0.736 seconds later at R2 129..255, and `0x05` arrived
at release with R2=0. The raw compatibility constants therefore change both
decoded intensity and start region; neither profile has hardware acceptance for
these parameters yet.

## Comparison mode

`--trigger-compare-semantic` requires `--trigger-dry-run`. On each changed
effect it logs both final mappings plus the current physical trigger positions:

```text
COMPARE R2: compat=mode=... semantic=mode=... \
  t=<monotonic> physical_l2=<0..255> physical_r2=<0..255>
```

The per-game wrapper mode `translation-dry-run` applies these fixed arguments:

```text
--trigger-dry-run --trigger-debug --hid-debug --trigger-compare-semantic
```

It cannot write ForceAdapt. Full HID debug provides the raw report needed for a
real replay fixture; comparison logging is deduplicated by the pair of mapping
decisions to keep the trace bounded.

## Decision after capture

Use one synchronized OW2 dry-run to decide each main effect:

1. preserve a compatibility special case when it matches hardware capability
   and produces the intended game change;
2. prefer the semantic candidate when the special case discards decoded
   region/intensity without compensating evidence;
3. retain an explicitly named approximation when APEX 4 cannot express the
   DualSense effect;
4. leave an effect unsupported rather than infer unsafe parameters.

Only the selected, documented profile proceeds to a mode-specific physical
test. The fixed mild/early-trigger gate remains a diagnostic tool and is not
part of this profile decision. For this OW2 vector, software evidence prefers
the semantic profile as the faithful decoded candidate, but does not establish
that rattle 32 or resistance 96 is physically acceptable. Mode 2 and mode 1
therefore each require explicit bounds in any authorization package; the old
resistance-mild authorization does not cover either candidate.

The first physical candidate keeps semantic rattle 32 and caps semantic
resistance 96 to the previously mild-tested strength 40. It preserves the game
mode transition and start region, but shares a one-second, one-cycle R2 budget;
it is explicitly a bounded semantic approximation. `native-dry-run` and
`native-write` select the same fixed policy, with only the former disabling the
transport. The write form remains unapproved and is not in the persisted Steam
option.

## Candidate status

Comparison candidate `d98d88c` passed 109 local tests and 108 SteamOS tests with
one compiler-dependent skip. A harmless translation session passed and the
runtime is deployed. The synchronized OW2 dry-run then supplied complete replay
vectors and three correlated action cycles; the local suite including the new
fixture passes 110 tests. Physical acceptance remains pending.

Bounded candidate `f3a1f57` passes 117 local tests and 116 SteamOS tests with
one compiler-dependent skip. Captured-report replay through the live virtual
controller under dry-run produced semantic mode 2, capped mode 1 and Normal.
It is deployed, but the launch option remains comparison-only dry-run.

The subsequently authorized single physical cycle produced both selected
modes, and the holder distinguished vibration from resistance. The one-second
deadline cleared before the later game Off. A strong sensation immediately
after release correlated with separate conventional rumble `(255,255)`, not
another translated trigger effect. The launch option was returned to
comparison-only dry-run after exit.

`ded4178` extends the same selected mapping into an Off-rearmed session without
changing its mode caps: at most three R2 cycles in 30 seconds, four seconds per
cycle, and twelve seconds possible active output. The fourth captured cycle is
rejected. Its write wrapper is deployed but absent from Steam configuration;
only a newly authorized physical block may select it.

The authorized three-cycle block subsequently passed: each captured OW2 action
produced mode 2, capped mode 1 and a game-Off Normal before the four-second
deadline, and the holder distinguished both modes with normal release after
all three cycles. This accepts the bounded semantic approximation for the
scoped OW2/2.4 GHz/R2 profile, not the uncapped semantic resistance 96 or the
compatibility rattle 120.

## Production OW2-safe profile

`85cb93b` turns the accepted behavior into a named continuous profile rather
than exposing the old compatibility translator as the public write path. It
accepts only these right-trigger patterns:

```text
0x26 ff030000000000001500 -> mode 2 (0,1,32,21,0)
0x21 ff039224491200000000 -> mode 1 (0,40,0,0,0)
0x05                      -> Normal and rearm
```

The required order is rattle, optional resistance updates, then Off. A cycle
that reaches four seconds is cleared bilaterally and cannot rearm until Off.
There is no three-cycle product limit; unknown bytes, L2, other modes and
out-of-order resistance are ignored. `ow2-safe-dry-run` and `ow2-safe-write`
use the same fixed policy. The old compatibility mapping is not reachable as a
live configuration profile.
