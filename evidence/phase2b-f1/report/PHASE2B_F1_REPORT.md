# Phase 2B first-block report

Counted live first-block evidence.

**First block complete; HOLD expansion.** A successful technical review and a separately applicable cumulative grant remain required. This report creates no spending authority.

Study `38132ee3a935af4ac975c3fda84154d1a85b1bcb510925f409993a15d3103d8b`. Task `nb-curated-9c418f063bc433264d29`, repeat 1.

```
Which 4-digit lock combination is the safest?
```

Source:
```
{
  "dataset": "NoveltyBench/curated",
  "revision": "64a23be6b18ec1dacc298830aab276061b6e143c",
  "source_sha256": "ca9b6f470e5d7f7e34a281e2fdaa6f6e51c38bdae075ea580d184139ec391fa7",
  "source_task_id": "curated-95"
}
```

Requests attempted: **28/55**; native orders present: **3/3** (**69 missing in the full 72-order study**). Usage-based public-price upper bound: **$0.210174**; unresolved reservation: **$0.000000**. These amounts are not provider invoice certification.

One prompt and one repeat do not establish a strategy winner. The unchanged whole-study benchmark decision is inconclusive, with null aggregate contrasts and no selected seed. No human, CrPO or recursive-adaptation result is inferred.

## Procedure and context

In the user's regenerate/in-context terms: **A independently regenerates each answer in a fresh context** containing the original prompt and fixed answer instruction. **B regenerates each answer in a fresh context conditioned on one planning angle**: it makes one ten-angle plan, then ten fresh answer requests, each receiving the original prompt plus its assigned angle. That angle is in-context guidance; the answer itself is newly generated. A/B answer calls do not see sibling answers. **C performs an in-context permutation, not answer resampling**: it sees the original prompt and ten saved B answers and returns only their order. For example, C may move saved B07 to position 1 without rewriting B07; an A or B regeneration creates a new answer text through a separate request. Thirty complete ordered presentations would therefore contain twenty generated texts. Each native grouping sees one whole portfolio; each quality head is judged alone against the original prompt.

Patience is 0.8. Later duplicates receive no quality call and contribute zero credited utility; their missing quality is not a fabricated zero score. Native saved metrics below are replayed unchanged. No fallback, repair, retry or replacement is performed.

## Actual request settings and returned models

Omitted parameters remain omitted; provider defaults are not reconstructed as observations. Exact contexts and canonical response records are included in first-block-data.json and the whitelisted raw archive.

### answer — 20 attempted requests

```
{
  "attempts": 20,
  "omitted_controls": [
    "temperature",
    "top_p",
    "top_k",
    "seed",
    "max_completion_tokens",
    "reasoning_effort"
  ],
  "requested_settings": {
    "inference_geo": "global",
    "max_tokens": 4096,
    "model": "claude-sonnet-5-5",
    "output_config": {
      "effort": "low"
    },
    "service_tier": "standard_only",
    "thinking": {
      "type": "adaptive"
    }
  },
  "returned_models": [
    "claude-sonnet-5-5"
  ],
  "role": "answer"
}
```
### plan — 1 attempted requests

```
{
  "attempts": 1,
  "omitted_controls": [
    "temperature",
    "top_p",
    "top_k",
    "seed",
    "max_completion_tokens",
    "reasoning_effort"
  ],
  "requested_settings": {
    "inference_geo": "global",
    "max_tokens": 4096,
    "model": "claude-sonnet-5-5",
    "output_config": {
      "effort": "low"
    },
    "service_tier": "standard_only",
    "thinking": {
      "type": "adaptive"
    }
  },
  "returned_models": [
    "claude-sonnet-5-5"
  ],
  "role": "plan"
}
```
### rank — 1 attempted requests

```
{
  "attempts": 1,
  "omitted_controls": [
    "temperature",
    "top_p",
    "top_k",
    "seed",
    "max_completion_tokens",
    "reasoning_effort"
  ],
  "requested_settings": {
    "inference_geo": "global",
    "max_tokens": 4096,
    "model": "claude-sonnet-5-5",
    "output_config": {
      "effort": "low"
    },
    "service_tier": "standard_only",
    "thinking": {
      "type": "adaptive"
    }
  },
  "returned_models": [
    "claude-sonnet-5-5"
  ],
  "role": "rank"
}
```
### group — 3 attempted requests

```
{
  "attempts": 3,
  "omitted_controls": [
    "temperature",
    "top_p",
    "top_k",
    "seed",
    "max_tokens",
    "max_completion_tokens",
    "reasoning_effort",
    "service_tier",
    "inference_geo",
    "thinking",
    "output_config"
  ],
  "requested_settings": {
    "model": "gpt-5.6-luna",
    "response_format": {
      "json_schema": {
        "name": "Partition",
        "schema": {
          "additionalProperties": false,
          "properties": {
            "groups": {
              "items": {
                "items": {
                  "type": "integer"
                },
                "type": "array"
              },
              "title": "Groups",
              "type": "array"
            }
          },
          "required": [
            "groups"
          ],
          "title": "Partition",
          "type": "object"
        },
        "strict": true
      },
      "type": "json_schema"
    }
  },
  "returned_models": [
    "gpt-5.6-luna"
  ],
  "role": "group"
}
```
### quality — 3 attempted requests

```
{
  "attempts": 3,
  "omitted_controls": [
    "temperature",
    "top_p",
    "top_k",
    "seed",
    "max_completion_tokens",
    "reasoning_effort",
    "service_tier",
    "inference_geo"
  ],
  "requested_settings": {
    "max_tokens": 16000,
    "model": "claude-opus-5",
    "output_config": {
      "effort": "high",
      "format": {
        "schema": {
          "additionalProperties": false,
          "properties": {
            "score": {
              "title": "Score",
              "type": "integer"
            }
          },
          "required": [
            "score"
          ],
          "title": "Score",
          "type": "object"
        },
        "type": "json_schema"
      }
    },
    "thinking": {
      "type": "adaptive"
    }
  },
  "returned_models": [
    "claude-opus-5"
  ],
  "role": "quality"
}
```
## Accounting

```
{
  "active_cumulative_cap_micro_usd": 20000000,
  "first_slot_coverage": {
    "not_needed_nonhead": 27,
    "ok": 28
  },
  "journal_status": "ready",
  "request_counts": {
    "answer": 20,
    "group": 3,
    "plan": 1,
    "quality": 3,
    "rank": 1
  },
  "reserved_micro_usd": 0,
  "unique_role_cost_micro_usd": {
    "answer": 141734,
    "group": 4800,
    "plan": 9894,
    "quality": 33792,
    "rank": 19954
  }
}
```

Candidate C's attributed generation cost includes its B parent plus ranking; the unique phase ledger charges those requests once. Missing portfolios keep candidate costs missing.

## Planner and reranker visible outputs

### plan: ok

```
{"angles":[{"id":"angle-01","angle":"Explain that safety depends on unpredictability, not any specific number: all 10,000 combinations are equally strong if chosen truly randomly, so recommend generating the code with dice, a random number generator, or a shuffled-digit method."},{"id":"angle-02","angle":"Present data-driven guidance on the most commonly chosen PINs (1234, 1111, 0000, 2580, 1004, 2000, etc.) from breach analyses, and explain that the 'safest' choice is one outside these high-frequency sets."},{"id":"angle-03","angle":"Cover human-pattern pitfalls: birthdays, years, anniversaries, keypad shapes, repeated or sequential digits, and phone-number fragments, with a checklist of categories to avoid and why attackers try them first."},{"id":"angle-04","angle":"Give a practical step-by-step procedure for creating a strong combination (roll a die/pick digits from a random source, check against a weak-list, avoid reuse across locks, test memorability), ending with one worked example method but not a recommended fixed number."},{"id":"angle-05","angle":"Discuss the math: 10,000 possibilities, expected brute-force time per attempt rate, how physical lock type (padlock vs. electronic keypad with lockout) changes real security, and why attempt limits matter more than digit choice."},{"id":"angle-06","angle":"Distinguish threat models: casual opportunist, shoulder-surfer, thief with time, or someone who knows you. Explain how the best 4-digit choice shifts (e.g., avoiding personal info, wear marks on keys, smudges) depending on who you defend against."},{"id":"angle-07","angle":"Focus on physical and mechanical weaknesses: wear patterns on keypad buttons, fingerprint smudges, resting positions on dial wheels, and manipulation of cheap combination padlocks, with advice on mitigating them like rotating digits and re-scrambling."},{"id":"angle-08","angle":"Advise on memory and management: how to remember a random code without writing it insecurely, using mnemonic or chunking techniques, periodically changing it, and not reusing it for bank cards or phones."},{"id":"angle-09","angle":"Argue that 4 digits is inherently limited and suggest alternatives for higher security: longer PINs, alphanumeric codes, key locks, biometric or smart locks, two-factor setups, while still answering what the best 4-digit option is."},{"id":"angle-10","angle":"Debunk myths and clarify the question: no universally 'safest' number exists, address the misconception that unusual-looking or 'random-looking' human-picked numbers are safe (e.g., 7294 chosen by hand), and explain why published 'safe' numbers become unsafe once popular."}]}
```
### rank: ok

```
{"order":["response-63d4c2bc2b3bf82d29f4fe78","response-c0bc5bcace5ea53061022747","response-f7db0c5fb74b60abeaf4f3bc","response-b1597f830ca657fa73009979","response-57d245b8b2d5cbde6d874096","response-350a7a1097801e3f7d199156","response-14b2d93e7556f38f75615128","response-72eb2aa140cc89889160186b","response-2b698fedabd19004e324e2a9","response-4376fa61e67febceea70f432"]}
```

## Order A — scored

```
{
  "candidate_generation_ranking_cost_micro_usd": 56570,
  "failure": null,
  "metrics": {
    "distinct": 1,
    "utility": 1.792464399362674
  }
}
```

| Position | Response ID | Original B position | Status | Group | Head | Quality | Quality coverage |
|---:|---|---:|---|---:|---|---:|---|
| 1 | response-3e22b62e043869968912f41a | — | ok | 0 | True | 8 | ok |
| 2 | response-0124505ff0f12446f41d001a | — | ok | 0 | False | — | not_needed_nonhead |
| 3 | response-66d43aca9801ad2641106e7d | — | ok | 0 | False | — | not_needed_nonhead |
| 4 | response-30f73008c7bc3072450a7b6e | — | ok | 0 | False | — | not_needed_nonhead |
| 5 | response-d99cc2df05d1ca80d4197722 | — | ok | 0 | False | — | not_needed_nonhead |
| 6 | response-3c0de3ecb0918de9337d2940 | — | ok | 0 | False | — | not_needed_nonhead |
| 7 | response-fb69d198d1cd906d4da91a20 | — | ok | 0 | False | — | not_needed_nonhead |
| 8 | response-32ecfe66280ece50f6e9dd94 | — | ok | 0 | False | — | not_needed_nonhead |
| 9 | response-18a0a9c47b87e2c53c8352e8 | — | ok | 0 | False | — | not_needed_nonhead |
| 10 | response-a3d3ce79f7849004f8946c4e | — | ok | 0 | False | — | not_needed_nonhead |

All visible answer texts, in this order; C repeats its unchanged B texts.

### A01 — response-3e22b62e043869968912f41a

```
No single 4-digit combination is inherently "safest," because if it's chosen truly at random, every combination has the same 1-in-10,000 chance of being guessed. What makes a combination weak is predictability. The safest choice is one that no attacker would try early.

**Safest approach:**
- Generate it randomly (dice, a random number generator, or a password manager). Roll a 10-sided die four times, or use a random generator.
- Don't pick it yourself, since people tend to choose patterns without realizing it.

**Avoid these, since they're guessed first:**
- Repeats and sequences: 0000, 1111, 1234, 4321, 2580 (straight down a keypad)
- Years and dates: birth years, birthdays (e.g., 1990, 0714), anniversaries, and years in the 1950-2030 range
- Common picks: 1004, 2000, 7777, 6969, 1212
- Anything tied to you: address digits, phone number endings, or the last four digits of your SSN
- Visual patterns on a keypad: corners, a straight line, a square

**Practical tips:**
- Don't reuse the same PIN across locks, phones, and cards.
- Change the default combination if the lock came with one.
- On a physical lock, scramble the dials after locking.
- Keep in mind that 4 digits is only 10,000 possibilities, so it can be brute-forced if an attacker has unlimited attempts and time. If the lock allows more digits, use more. For high-value items, choose a lock with a key or a longer code.

An example of a decent combination would be something like 7306 or 4918, but don't use those exact ones now that they're written publicly. Generate your own.
```
### A02 — response-0124505ff0f12446f41d001a

```
No single 4-digit combination is inherently "the safest," because a truly random code is as strong as any other. What matters is that the code is unpredictable. Of the 10,000 possible combinations, the weak ones are those people commonly choose.

**Safest approach:**
- Generate the digits randomly (dice, a random number generator, or drawing numbers from a hat) rather than picking digits that "feel" random. Humans tend to choose patterns.

**Avoid these common choices:**
- Repeated or sequential digits: 0000, 1111, 1234, 4321, 2468
- Years and dates: birth years, anniversaries (1985, 0704), or any year from roughly 1940 to 2030
- Keypad patterns: 2580 (straight down the middle), 1357, corners
- Famous numbers: 1004, 2000, 6969, 7777, 1212
- Anything tied to you: phone digits, address, or street number

Around 10-15% of people reportedly use 1234 or 1111, and these are the first guesses of anyone attempting to break in.

**Practical tips:**
- Change the factory default code immediately (often 0000 or 1234).
- Don't reuse the same PIN across multiple locks or cards.
- Check for wear: on a keypad, if only four keys look worn or greasy, an observer knows the digits and only has to try 24 orderings. Using a code with a repeated digit reduces this risk.
- If you can, choose a lock with lockout after failed attempts, since 4 digits is weak against brute force (10,000 tries) on a mechanical dial lock.
- For anything valuable, consider a longer code (6+ digits) or a different type of lock.

If you want a quick random choice, something like 7302 or 5816 would be fine, as long as you generate it randomly yourself and don't use an example from a public answer like this one.
```
### A03 — response-66d43aca9801ad2641106e7d

```
There is no single "safest" combination, but the safest choice is one that is random and not guessable.

**Why randomness matters:** There are 10,000 possible combinations (0000-9999). Attackers don't try them evenly. They start with the most common ones, so any pattern a human would pick is weaker.

**Avoid these (most commonly used):**
- Repeats and sequences: 0000, 1111, 1234, 4321, 2580 (straight down the keypad's middle)
- Years and dates: 1990, 2005, birthdays (e.g., 0412), anniversaries
- Patterns on the keypad: 1357, 2468, shapes or corners
- Anything tied to you: address digits, phone number endings, part of your ZIP code
- Lock defaults: 0000 or 1234 on many new locks

**How to pick a strong one:**
1. Generate it randomly: roll a die or draw digits from a shuffled set, or use a random number generator. Phone apps or a password manager can do this.
2. Skip obvious structure: avoid pairs like 3838, ascending/descending runs, or all the same digit.
3. Make it memorable only to you, without a connection others could discover. One approach is to generate a random number and then memorize it with a mental image or phrase.
4. Don't reuse it across locks, such as your phone, luggage, and gym locker.

**Practical notes:**
- With only 10,000 possibilities, a 4-digit lock is weak against anyone who can try combinations repeatedly. A random code mostly protects against casual or opportunistic attempts.
- For high-value items, use a longer code, a key lock, or a lock with attempt limits.
- Change the combination if you suspect someone saw you enter it.

**Bottom line:** the safest 4-digit combination is a truly random one that has no personal connection to you and doesn't follow a recognizable pattern.
```
### A04 — response-30f73008c7bc3072450a7b6e

```
There is no single "safest" combination, but the safest choice is one that is **random and not guessable**. Any 4-digit code has the same 1-in-10,000 chance of being hit by a blind guess, but real attackers don't guess blindly. They try common codes first.

**What makes a combination weak (avoid these):**
- Repeated or sequential digits: 0000, 1111, 1234, 4321, 2580 (straight down a keypad)
- Years and dates: 1990, 2001, birthdays (e.g., 0412), anniversaries
- Common PINs: 1004, 2000, 7777, 6969
- Patterns on the keypad: corners, lines, or an "L" or "Z" shape
- Anything tied to you: phone number digits, address, or part of your ID

Roughly a quarter or more of people use one of a small set of codes, so those are tried first.

**What makes a combination strong:**
- **Generate it randomly.** Use a random number generator, dice (roll a 10-sided die four times), or draw numbers from a hat. Don't pick one you think "feels random," since humans pick predictably.
- Avoid patterns, with digits that don't repeat or run in order.
- Use a different code for each lock or account.
- Don't use a code that's been exposed or shared widely, and change it if someone may have seen it.

**Practical notes:**
- With only 10,000 possibilities, a physical lock can be brute-forced given time and access, so a 4-digit lock is only a deterrent. For anything valuable, use a lock with more digits or a key, or add other layers of protection.
- Check for wear on the dials or buttons, which can reveal which digits are used on some keypad locks.
- If the lock allows lockout or delay after failed attempts (like a phone or smart lock), that protects you more than the code itself.

If you want, I can suggest how to generate a random code with dice, or help you pick a code strategy for a specific type of lock.
```
### A05 — response-d99cc2df05d1ca80d4197722

```
There is no single "safest" combination, but the safest choice is one that is random and not guessable. Here is what matters:

**Pick one that is:**
- **Randomly generated.** Use a random number generator, dice, or the shuffle on a set of numbered cards. Humans choose predictable patterns even when they try not to.
- **Unique to that lock.** Don't reuse your phone PIN, bank PIN, or other codes.

**Avoid these common choices:**
- Repeats and sequences: 0000, 1111, 1234, 4321, 2580 (the keypad's middle column)
- Years and dates: birth years, anniversaries, 1990-2025 (these make up a large share of PINs)
- Patterns on the keypad: 1357, 2468, shapes like corners or an "L"
- Anything tied to you: address digits, phone number endings, or a partial ID number

**Why it matters:** There are 10,000 possible combinations (0000-9999). Studies of leaked PINs show that a small set, such as 1234, 1111, 0000, 1212, and 7777, accounts for a notable share of all PINs people use. A random code avoids those hot spots, so an attacker has no better strategy than trying all 10,000.

**Practical tips:**
- Make sure the digits aren't obviously patterned after you generate them. Re-roll if you get something like 1212.
- If you worry about forgetting it, store it in a password manager rather than choosing something memorable and guessable.
- Remember that a 4-digit lock only offers limited protection. For anything valuable, consider a longer code or a keyed or different type of lock, since a determined person can brute-force 10,000 combinations in a reasonable time.

If you want, I can explain how to generate one with dice.
```
### A06 — response-3c0de3ecb0918de9337d2940

```
There's no single "safest" combination, but the safest choice is one that's **random and not guessable**. Here's what matters:

**What makes a 4-digit code strong**
- **Randomly generated:** Pick digits using a random method (dice, a random number generator, or a password manager), not something that feels "random" to you.
- **Not personal:** Avoid birthdays, anniversaries, years, addresses, or phone number digits.
- **Unique:** Don't reuse it across locks, phones, or cards.

**Combinations to avoid** (these are the most commonly used and tried first)
- 1234, 0000, 1111, 2222, and other repeated digits
- 4321, 1212, 2580 (a straight line on keypads), 6969
- Years like 1990-2025
- Patterns like 1357, 2468, or shapes on the keypad

**Reality check**
There are only 10,000 possible codes, so any 4-digit lock can be brute-forced quickly if an attacker has unlimited tries and physical access. A random code is the best you can do within that limit, but for real security:
- Use locks that limit attempts or lock out after failures (phones, smart locks)
- Use a longer code (6+ digits) where possible
- For physical padlocks, consider a keyed lock or one with more dials

**Quick method:** Roll a 10-sided die four times, or use a random number generator, and write the result down somewhere safe if you worry about forgetting it.
```
### A07 — response-fb69d198d1cd906d4da91a20

```
There is no single "safest" combination, but the safest choice is one that is random and not based on anything guessable.

**What makes a 4-digit code strong**
- **Randomly generated**: Pick digits using a random method (dice, a random number generator, or drawing numbers from a hat). Every random code is equally strong, since there are 10,000 possibilities.
- **No personal meaning**: Avoid birthdays, anniversaries, addresses, phone number digits, and years.
- **No patterns**: Avoid sequences, repeats, and keypad shapes.

**Combinations to avoid (most commonly used, so guessed first)**
- 1234, 0000, 1111, 2222, and other repeated digits
- 1212, 2580 (straight down the keypad), 4321
- 2000, 2001, and other recent years
- 6969, 1004, 7777

**Practical tips**
- Don't reuse the same code across multiple locks, phones, or cards.
- Shield the dial or keypad when entering it.
- On a mechanical lock, scramble the dials after locking, and avoid leaving them near the combination.
- Don't store the code in an obvious place, such as a note in your wallet next to the card it unlocks.
- If you can, choose a lock that lets you use more digits, since each extra digit multiplies the possibilities by 10.

**Reality check**: A 4-digit lock only offers 10,000 combinations, so it deters casual snooping but can be brute-forced in minutes by someone determined. For anything valuable, use a longer code or a higher-security lock.
```
### A08 — response-32ecfe66280ece50f6e9dd94

```
There is no single "safest" combination, but the safest choice is one that is **random and unpredictable**. Here's what matters:

**What makes a 4-digit code strong**
- **Randomly generated**: Pick digits with a random number generator, dice, or by drawing numbers from a hat. Any truly random code is as safe as any other, with 10,000 possibilities.
- **No personal meaning**: Avoid birthdays, anniversaries, addresses, phone numbers, or years.
- **Not used elsewhere**: Don't reuse your phone, bank card, or other PINs.

**Combinations to avoid** (the most commonly chosen, so the first ones guessed)
- 1234, 0000, 1111, 2222, and other repeated digits
- 4321, 2580 (the middle column of a keypad), 1212, 6969
- Years like 1990-2025
- Patterns such as 1357, 2468, or shapes on the keypad

**Practical tips**
- Wear patterns: on a physical lock or keypad, worn buttons can reveal which digits are used, so choose a code with different digits if you can.
- Use a lock that limits guesses: a keypad or phone lock with attempt limits or lockouts makes even a 4-digit code much harder to crack than a mechanical dial or wheel lock, which can be brute-forced.
- Change it periodically if it's protecting something valuable, or if someone may have seen you enter it.
- For high-value items, consider a longer code (6+ digits) or a different type of lock altogether, since 4 digits is inherently limited.

**Quick method**: Roll a 10-sided die four times, or use your device's random number generator, and use the result, unless it forms an obvious pattern, in which case re-roll.
```
### A09 — response-18a0a9c47b87e2c53c8352e8

```
There is no single "safest" combination, but the safest choice is one that is **random and not guessable**. Any 4-digit code has 10,000 possibilities, so what matters is avoiding the combinations people and attackers try first.

**Avoid these (most commonly used):**
- 1234, 0000, 1111, 2222, and other repeated digits
- 1004, 2000, 4321, 1212, 7777
- Years and dates: birth years (1985), birthdays (0614), anniversaries, current year
- Patterns on the keypad: 2580 (straight down the middle), 1357, corners, or shapes
- Your PIN for other things, or the last 4 digits of your phone number or address

**Choose instead:**
- A code generated randomly (use a random number generator, dice, or a password manager), not one you "make up," since people's invented codes tend to follow patterns
- A code with no connection to your personal information
- Four different digits with no ascending or descending runs (e.g., 7302 is better than 1234 or 3333)

**Practical tips:**
- Don't reuse the same code across multiple locks, phones, and cards.
- Change the code from the factory default (often 0000).
- Check for wear: on a lock used a lot, worn buttons can reveal which digits are used. Change it occasionally.
- If the lock allows longer codes, use 6 digits or more.

A 4-digit lock is only moderately secure at best, since it can be brute-forced in a short time on many mechanical locks (up to 10,000 tries). For anything valuable, use a lock with more digits, a key, or a stronger mechanism.
```
### A10 — response-a3d3ce79f7849004f8946c4e

```
There is no single "safest" combination, but the safest choice is one that is random and unpredictable. What matters is avoiding the patterns people tend to pick.

**Safest approach:**
- Generate the digits randomly (dice, a random number generator, or drawing numbers from a hat) rather than choosing digits that feel memorable.
- Every truly random 4-digit code is equally strong, with 10,000 possibilities.

**Avoid the most commonly guessed codes:**
- 1234, 0000, 1111, 2222 and other repeated digits
- 1212, 2580 (straight down a keypad), 4321
- Years and dates, especially birth years (1985, 2001) and anniversaries
- Patterns that form shapes on the keypad, such as corners or a box
- Codes from phone numbers, addresses, or other personal information

**Practical tips:**
- Don't reuse the same code across multiple locks, cards, or phones.
- Avoid wear patterns: on a keypad, if only four buttons show smudges or wear, the possibilities shrink to 24 arrangements. Where possible, change the code occasionally.
- For a combination lock with dials, spin the dials thoroughly after locking.

**Reality check:** A 4-digit code has only 10,000 combinations, so it protects against casual tampering but not a determined attacker with unlimited attempts. For anything valuable, use a longer code (6+ digits) or a lock with a different security mechanism, such as a key or a lockout after failed attempts.
```

## Order B — scored

```
{
  "candidate_generation_ranking_cost_micro_usd": 95058,
  "failure": null,
  "metrics": {
    "distinct": 1,
    "utility": 1.5684063494423397
  }
}
```

| Position | Response ID | Original B position | Status | Group | Head | Quality | Quality coverage |
|---:|---|---:|---|---:|---|---:|---|
| 1 | response-63d4c2bc2b3bf82d29f4fe78 | — | ok | 0 | True | 7 | ok |
| 2 | response-c0bc5bcace5ea53061022747 | — | ok | 0 | False | — | not_needed_nonhead |
| 3 | response-350a7a1097801e3f7d199156 | — | ok | 0 | False | — | not_needed_nonhead |
| 4 | response-72eb2aa140cc89889160186b | — | ok | 0 | False | — | not_needed_nonhead |
| 5 | response-f7db0c5fb74b60abeaf4f3bc | — | ok | 0 | False | — | not_needed_nonhead |
| 6 | response-57d245b8b2d5cbde6d874096 | — | ok | 0 | False | — | not_needed_nonhead |
| 7 | response-2b698fedabd19004e324e2a9 | — | ok | 0 | False | — | not_needed_nonhead |
| 8 | response-4376fa61e67febceea70f432 | — | ok | 0 | False | — | not_needed_nonhead |
| 9 | response-b1597f830ca657fa73009979 | — | ok | 0 | False | — | not_needed_nonhead |
| 10 | response-14b2d93e7556f38f75615128 | — | ok | 0 | False | — | not_needed_nonhead |

All visible answer texts, in this order; C repeats its unchanged B texts.

### B01 — response-63d4c2bc2b3bf82d29f4fe78

```
No single 4-digit combination is inherently the safest. If a code is chosen truly at random, all 10,000 possibilities (0000-9999) are equally strong. What makes a code weak is predictability, not the digits themselves.

**Why people's picks are weak:** Humans gravitate toward patterns like 1234, 0000, 1111, birth years, and dates. Attackers try these first, so a "random-looking" code you chose yourself is often far easier to guess than a truly random one.

**How to pick a safe one:**
- **Dice:** Roll a 10-sided die four times, or roll a 6-sided die and re-roll any 7-9 equivalents (e.g., use a method that maps results to 0-9 without bias).
- **Random number generator:** Use a password manager or a trusted RNG to generate four digits.
- **Shuffled digits:** Write 0-9 on slips of paper, draw one, record it, and replace it. Repeat four times. (Replacing matters, since repeated digits are allowed.)

**Avoid:**
- Sequences, repeats, or keypad patterns (1234, 2580, 7777)
- Dates, ages, addresses, phone digits
- Reusing the same code across multiple locks or cards

**Caveats:** A 4-digit code has only 10,000 possibilities, so it can be brute-forced if an attacker has unlimited attempts. Random selection is the best you can do within that limit, but for anything valuable, use a longer code, a lock with attempt limits, or a different security method.
```
### B02 — response-c0bc5bcace5ea53061022747

```
No single 4-digit combination is inherently the safest. What matters is how unpredictable it is, and the safest combination is one that attackers are least likely to guess early.

**Most commonly used PINs (avoid these)**
Analyses of leaked password and PIN datasets consistently show heavy clustering on a small set:
- 1234 (by far the most common, roughly 10% of all PINs in some studies)
- 1111, 0000, 1212, 7777
- 2580 (the straight vertical line down a keypad)
- 1004 (popular in Korea, "cheonsa," meaning angel)
- 2000, 2001, and other years
- Birth years (19xx) and dates in MMDD or DDMM format
- Repeating or sequential patterns (4321, 2222, 1122)

Together, just the top 20 or so PINs account for a large share of all choices. That means an attacker who tries a handful of guesses has a real chance of getting in.

**What makes a PIN safer**
- **Random selection:** Generate the digits with a random method (a password manager, dice, or a random number generator) rather than choosing something meaningful.
- **Avoid patterns:** Skip keypad shapes, repeated digits, ascending or descending runs, and anything resembling a date.
- **Avoid personal data:** Birthdays, anniversaries, addresses, and phone number fragments are easy to guess if someone knows you.
- **Don't reuse:** Use a different PIN for each lock or card.

**Reality check**
There are only 10,000 possible combinations, so a 4-digit lock can't resist a determined brute-force attempt. Even a perfectly random PIN is only safe where attempts are limited, such as ATMs and phones that lock after a few tries. A basic mechanical combination lock can be cycled through all 10,000 options in a short time. For anything valuable, use a longer code (6+ digits) or a lock with a different security mechanism.

**Bottom line:** The safest 4-digit combination is a randomly generated one that isn't in the common-PIN lists above.
```
### B03 — response-350a7a1097801e3f7d199156

```
No single 4-digit combination is "safest" in the abstract, because every code has the same 1-in-10,000 chance of being guessed at random. The safest code is one that's chosen randomly, so it doesn't fall into the patterns attackers try first. Here is a checklist of categories to avoid and why.

**Categories to avoid**

1. **Birthdays and dates (e.g., 0412, 1987):** Anyone who knows or can find your birthday, or that of a partner, child, or parent, can guess these quickly. Many codes are in MMDD or DDMM format.
2. **Years (1990-2025):** Birth years, graduation years, and the current year are heavily overrepresented, so attackers try them early.
3. **Anniversaries and significant dates:** Weddings, move-in dates, and similar events are often discoverable from social media.
4. **Repeated digits (0000, 1111, 7777):** These are always among the first guesses.
5. **Sequential digits (1234, 4321, 2345, 9876):** Extremely common and always tested early.
6. **Keypad shapes and patterns:** Straight lines (2580), corners (1397), squares (1245), and "X" or "L" shapes. They are easy to remember, which is exactly why many people choose them.
7. **Phone number fragments:** The last four digits of your phone number, a former number, or a family member's number. These are easy for someone who knows you to find.
8. **Addresses and ZIP codes:** House numbers, street numbers, or ZIP codes are tied to you and easy to look up.
9. **Repeated pairs and mirrors (1212, 6969, 1221):** These are common and predictable.
10. **Pop-culture or meme numbers (007, 1337, 8008, 4200):** Popular enough to appear on common-code lists.
11. **Lucky numbers or jersey numbers:** Personal, and often guessable by people who know you.
12. **PIN reuse:** Using the same code as your bank card, phone, or another lock means one leak exposes everything.

**Why attackers try these first**

Leaked-PIN datasets show that a small number of codes make up a large share of real-world usage. Attackers try the most common codes and personal-information guesses first, so a code with a meaningful pattern may be broken in far fewer than 10,000 attempts.

**How to choose a safe one**

- Generate it randomly: use a random number generator, dice (four rolls of a 10-sided die), or a password manager.
- Check it against the list above and re-roll if it resembles any category.
- Don't use anything derived from personal information.
- Use a unique code for each lock or device.
- If you can, choose a lock that limits guess attempts. A 4-digit code is weak against unlimited brute-force guessing, even if it's random.
- For high-value protection, use a longer code (6+ digits) if the lock allows it.

**Bottom line:** the safest combination is a random one you haven't used anywhere else and that doesn't match any of the patterns above.
```
### B04 — response-72eb2aa140cc89889160186b

```
No single 4-digit combination is "the safest." If a specific number were widely recommended, it would become a popular choice and therefore a weak one. What makes a combination safe is how it was chosen: randomly, and not reused. Here's a practical procedure.

**Step-by-step procedure**

1. **Generate each digit randomly.** Don't pick digits that "feel" random, because people favor birthdays, repeated digits, and patterns. Use a 10-sided die, a random number generator (a password manager's PIN generator works), or draw numbered slips from a bag. If you only have a six-sided die, roll it and discard 0 and any results you can't map, or use two rolls (see the worked example below).

2. **Check against a weak list.** Reject the combination if it is:
   - A repeat or sequence (0000, 1111, 1234, 4321, 2468)
   - A pattern on the dial or keypad (2580, 1357, 1212, 6969)
   - A year or date (1990, 2024, 0704, or anything resembling a birthday or anniversary)
   - Tied to you (address digits, phone digits, old PINs)
   - A common "famous" number (1004, 2000, 7777, 8888)

   If it fails, reroll the whole number instead of tweaking it, since tweaking reintroduces human bias.

3. **Don't reuse it.** Use a different combination for each lock, and never reuse your bank card PIN or phone passcode. If one lock is compromised or observed, the others stay safe.

4. **Test memorability.** Rehearse it a few times today, then again after a day and after a week. If you can't recall it, store it securely (a password manager or a locked note) instead of weakening it. Don't write it on the lock, your wallet, or a sticky note nearby.

5. **Limit exposure.** Shield the dial or keypad when entering it, scramble the dial after locking, and change the combination if someone may have seen it or if you've shared it.

**Worked example method (using a six-sided die)**

To get one digit from 0-9 with a standard die:
- Roll the die twice.
- If the first roll is 1-3, the digit's range is 0-4; if it's 4-6, the range is 5-9.
- Use the second roll to pick within the range: rolls 1-5 map to the 1st through 5th digit of the range; if you roll a 6, reroll.

Example: first roll 5 → range 5-9. Second roll 3 → third value in that range → **7**.

Repeat four times to get four digits, then run the weak-list check from step 2. If the result passes, that's your combination. If not, start over.

**Note:** With only 10,000 possibilities, a 4-digit lock can be brute-forced by anyone with unlimited access and time. Random selection protects against guessing, but for high-value items, choose a lock with more digits or a key-based or limited-attempt mechanism.
```
### B05 — response-f7db0c5fb74b60abeaf4f3bc

```
**Short answer:** Any combination chosen truly at random is equally safe. Mathematically, no 4-digit code beats another. What makes a code unsafe is that humans pick predictable ones.

**The math**
- There are 10^4 = 10,000 possible codes (0000-9999).
- A random code has a 1-in-10,000 (0.01%) chance of being guessed on any single try.
- Expected attempts to brute-force: on average about 5,000 (half the space); worst case 10,000.

**Time to brute-force by attempt rate**
- Manual padlock, ~1 try per 3 seconds: ~4 hours on average, ~8 hours worst case.
- Fast manual or a practiced thief, ~1 try/second: ~1.4 hours average, ~2.8 hours worst case.
- Automated device with no lockout, ~10 tries/second: ~8 minutes average.
- Electronic keypad with lockout (e.g., 5 tries, then a 30-minute delay): ~5,000 average attempts × 6 min per try after the first 5 means days to weeks, and a wipe-after-10 policy makes it effectively impossible.

**Why the lock type matters more than the digits**
- **Mechanical padlock/bike lock:** There's no attempt limit, so security is purely the 10,000-code space plus the thief's patience. Some can also be defeated by feel or by sensing slight binding in the wheels, which shrinks the effective search.
- **Electronic keypad with lockout or wipe:** The attacker gets only a few guesses, so the chance of success is tiny: with 3 attempts it's 0.03%. Here, avoiding common codes is what matters.
- **Phone/ATM PINs:** Attempt limits and escalating delays make 4 digits adequate for most threats.

**Where human choice breaks the math**
People cluster on a small set of codes. Studies of leaked PINs show 1234, 1111, 0000, 1212, 7777, and birth years (19xx/20xx) account for a large share. If an attacker gets only 3 tries, guessing the most common codes succeeds noticeably more than 0.03%, often around 4-10%. Other weak patterns include dates (MMDD), repeated pairs, keypad patterns (2580), and anything tied to you (address, phone digits).

**What to do**
1. Generate the code randomly (dice, a random generator, or a password manager), not from memory aids like dates.
2. Avoid the common patterns above.
3. Prefer devices with attempt limits, lockouts, or wipe features. A limit of 10 tries makes digit choice nearly irrelevant for a random code.
4. If the asset is valuable and there's no attempt limit, use a longer code (6 digits = 1,000,000 possibilities) or a key-based lock.

**Bottom line:** The safest 4-digit combination is a randomly generated one that isn't on common lists, and the safest *setup* is one where the lock limits guesses.
```
### B06 — response-57d245b8b2d5cbde6d874096

```
No single 4-digit combination is "safest" in the abstract. With 10,000 possibilities, any code chosen truly at random is equally strong. What changes is who you're defending against, and that determines which codes to avoid.

**The baseline: a random code**
Pick digits with a random method (dice, a random number generator, or digits from a shuffled deck), not your head. Humans pick predictable numbers. Roughly 10% of people use 1234, 1111, or 0000, and birth years (19xx/20xx) and dates are heavily over-represented.

**Threat model 1: Casual opportunist (guessing quickly)**
- Tries the most common codes: 1234, 0000, 1111, 2580, 1004, 2000, 4321, 6969, 1212, and years like 1990.
- Defense: avoid any pattern, repeated digit, sequence, keypad shape, or recent year. Any random code works.

**Threat model 2: Shoulder-surfer**
- Sees or films you entering it. Randomness doesn't help here.
- Defense: shield the keypad, avoid obvious finger movement patterns, and prefer codes without easy visual shapes. Codes with repeated digits (e.g., 7377) are easier to remember after a glimpse, so avoid them. Change the code if you suspect it was seen.

**Threat model 3: Thief with time (physical inspection or brute force)**
- Looks for wear marks, smudges, or faint sounds and clicks. On a keypad with only four worn buttons, the attacker needs to try only 24 orderings (or 12 if one digit repeats).
- Defense: don't leave the same 4 keys visibly worn or greasy. Wipe the keypad, and where the lock allows it, use a code with a repeated digit only if the keys aren't distinguishable. On mechanical wheel locks, scramble the wheels after use. If possible, choose a lock with lockout or tamper protection, or a longer code. Brute force of 10,000 codes takes only hours at a few seconds each, so for high-value items 4 digits is the real weakness.

**Threat model 4: Someone who knows you**
- Tries birthdays, anniversaries, addresses, phone digits, PINs you reuse, and meaningful numbers (a jersey number, a childhood home).
- Defense: use nothing connected to you, and never reuse a bank PIN. A random code beats a clever personal one.

**Bottom line**
- Best general choice: a randomly generated code with no repeats, no sequence, no personal meaning, not reused elsewhere.
- Against observers and wear marks, behavior (shielding, wiping, rescrambling) matters more than which digits you choose.
- If the stakes are high, 4 digits aren't enough. Use a longer code, a key lock, or a lock with lockout.
```
### B07 — response-2b698fedabd19004e324e2a9

```
There is no single "safest" combination, but the safest choice is a random one, and how you handle it physically matters nearly as much as which digits you pick.

**Picking the combination**
- Generate it randomly (dice, a random number generator, or draw digits from a shuffled deck). Avoid birthdays, years, repeats like 1111, sequences like 1234, and keypad patterns like 2580 or 1397.
- Any random 4-digit code gives 10,000 possibilities, so no code is inherently stronger than another. Strength comes from not being guessable.
- Avoid codes using four distinct digits only if you worry about wear (see below). Distinct digits are generally better, though they reduce the pool slightly to 5,040.

**Physical and mechanical weaknesses**

*Keypad wear and smudges*
- Frequently pressed buttons show wear, shiny spots, or fingerprint residue. With four distinct worn keys, an attacker only has 24 orderings to try.
- Mitigation: wipe the keypad regularly, and consider a code that repeats a digit (e.g., 3-7-3-9) so that only three keys show wear, though note this still leaves a small search space. Better yet, where the device allows it, use a longer code (6+ digits).
- Touch your keys with a fingertip pattern that also touches other keys or wipe after use, so residue doesn't reveal the code.

*Dial and wheel locks*
- Don't leave wheels resting on the combination digits. After opening, spin each wheel to a random position so the code isn't displayed.
- Cheap padlocks often have manufacturing tolerances that allow feeling for slight resistance on each wheel, or reading a binding wheel by applying tension to the shackle. Choose higher-quality locks with tighter tolerances, and avoid cheap ones for anything valuable.
- Pick codes whose digits aren't all adjacent to each other on the wheels' starting positions, such as 0000, since owners often leave these as the factory default.

*Changing the default*
- Always change the factory code (commonly 0000 or 1234).

**Habits**
- Re-scramble every time after locking: spin all wheels or clear the keypad entry.
- Shield the keypad from view while entering the code, since shoulder surfing and cameras are more common than lock manipulation.
- Change the code periodically, especially if it's shared or if you notice wear.
- For high-value protection, use a lock with a limited-attempt lockout, a longer code, or a key/biometric option instead of a 4-digit code.

**Bottom line:** choose a randomly generated code with no personal meaning, change it from the default, keep the keypad clean, scramble dials after each use, and use a better lock when the contents matter.
```
### B08 — response-4376fa61e67febceea70f432

```
There's no single "safest" 4-digit combination. If you pick one that's widely known, it's weak, but any code chosen at random is equally strong. With only 10,000 possibilities, the goal is to avoid predictable choices and manage the code well.

**Choose it randomly**
- Generate the digits with dice, a random number generator, or by drawing numbers from a hat. Don't choose by feel, since people gravitate toward patterns.
- Avoid the common picks: 1234, 0000, 1111, 2580, birth years, birthdays (like 0412), anniversaries, and repeated or sequential digits.

**Remember it without writing it insecurely**
- **Chunk it:** Split 7351 into "73" and "51," and tie each pair to something meaningful only to you, like a house number or a jersey number you'd never associate with yourself publicly.
- **Use a mnemonic:** Turn the digits into a mini-story or image. For example, 7-3-5-1 could be "seven swans swam past five... one boat." The odder the image, the better it sticks.
- **Use a phone-keypad word:** Pick a word that maps to four digits (e.g., "BLUE" is 2583) and remember the word. Don't use a word tied to you personally.
- **Practice with spaced repetition:** Recall it after a few minutes, then a day, then a week. After that it's usually permanent.
- If you must record it, store it in a reputable password manager, not on a sticky note, in your notes app, or in your wallet. Don't store it next to the lock.

**Manage it over time**
- Change it periodically, especially if someone may have seen you enter it, if you've shared it, or if the lock shows wear on certain buttons or dials.
- Don't reuse it for bank cards, phone unlock, alarm systems, or other locks. One leak or shoulder-surf would then expose everything.
- Shield the lock when entering it, and scramble the dials afterward.

**A caveat**
A 4-digit combination only deters casual access. A determined person can brute-force 10,000 options in a short time, so for anything valuable, choose a lock with a longer code, a key, or a stronger mechanism.
```
### B09 — response-b1597f830ca657fa73009979

```
There is no single "safest" 4-digit combination. The safest one is a random one, because any fixed answer I give you (or anyone else gives) becomes a bad choice the moment it's published.

**Best 4-digit approach**
- Generate the digits randomly (dice, a random number generator, or a password manager) instead of choosing a pattern you find memorable.
- Avoid the most commonly used codes: 1234, 1111, 0000, 2580, 1212, 2000, 7777, and 4321.
- Avoid birthdays, anniversaries, years (1950-2025), and anything tied to your address or phone number.
- Don't reuse the code across locks, phones, or bank cards.
- Avoid keypad patterns like straight lines, corners, or repeated pairs.

**Why 4 digits is inherently limited**
There are only 10,000 possible combinations. A person can try them all in a few hours on a mechanical lock, and software can do it in seconds if there's no attempt limit. Even a perfectly random 4-digit code is weak against anyone who can try guesses repeatedly. Physical wear on keys or buttons can also reveal which digits you use, shrinking the search space further.

**Better alternatives**
- **Longer PINs:** 6 digits gives 1,000,000 combinations, and 8 digits gives 100,000,000.
- **Alphanumeric codes:** Letters plus numbers increase the possibilities enormously, even at modest length.
- **Key locks:** A quality pick-resistant cylinder lock removes guessing as an attack and suits many physical uses.
- **Biometric or smart locks:** Fingerprint or app-based locks with attempt limits and lockout delays are far harder to brute force, especially with a PIN fallback that is long.
- **Two-factor setups:** Combine something you know (a code) with something you have (a key, phone, or card) so a guessed code alone isn't enough.

**Bottom line**
If you're stuck with 4 digits, pick a truly random one, avoid the common ones, and make sure the device limits wrong attempts. If the thing you're protecting is valuable, move to a longer code, a key, or a multi-factor lock.
```
### B10 — response-14b2d93e7556f38f75615128

```
No single 4-digit combination is "the safest." Here's why, and what to do instead.

**The core point:** Any 4-digit code has 10,000 possibilities (0000-9999). If the code was chosen truly at random, every one is equally hard to guess. A "safest" number only exists relative to how people choose, not in the math.

**Myth 1: "Random-looking" numbers I pick myself are safe.**
Numbers like 7294 feel random, but humans are bad at randomness. We avoid repeats, favor certain digits (like 7), avoid round patterns, and often unconsciously use dates, phone digits, or keyboard shapes. Attackers know these biases and try the most common choices first. A hand-picked code is only as strong as it is unpredictable to someone who knows how people think.

**Myth 2: Lists of "safest" codes solve the problem.**
Once a number is published as safe, it becomes popular, and popularity is exactly what makes a code unsafe. If a article names 7294 as the best code, people will use it, and attackers will add it to their guess list. Any code that is recommended widely is no longer a good choice.

**Myth 3: Avoiding 1234 and 0000 is enough.**
That's necessary but not sufficient. Birth years (19xx, 20xx), dates (MMDD), repeated pairs (6969), and patterns on the keypad are also heavily guessed.

**What actually makes a code safe:**
- **Generate it randomly:** use dice, a random number generator, or a password manager rather than picking it yourself. Roll a die-like process four times (a 10-sided die or a random generator).
- **Don't reuse it:** use different codes for different locks, phones, and cards.
- **Avoid personal info:** no birthdays, addresses, anniversaries, or the last digits of a phone number.
- **Don't share the method:** keep it unpredictable, and don't use the same code you've seen suggested.
- **Consider physical factors:** on a keypad, worn keys can reveal which digits are used, so change codes periodically. On a mechanical lock, set it away from the default.
- **Limit attempts where possible:** the real protection for phones and cards is lockout after a few wrong guesses, which matters far more than which number you choose.

**Bottom line:** the safest 4-digit combination is one generated randomly by you, known only to you, and not taken from any list, including this one. And if the item truly matters, a 4-digit code is a weak barrier regardless, so use a longer code or a stronger lock.
```

## Order C — scored

```
{
  "candidate_generation_ranking_cost_micro_usd": 115012,
  "failure": null,
  "metrics": {
    "distinct": 1,
    "utility": 1.5684063494423397
  }
}
```

| Position | Response ID | Original B position | Status | Group | Head | Quality | Quality coverage |
|---:|---|---:|---|---:|---|---:|---|
| 1 | response-63d4c2bc2b3bf82d29f4fe78 | 1 | ok | 0 | True | 7 | ok |
| 2 | response-c0bc5bcace5ea53061022747 | 2 | ok | 0 | False | — | not_needed_nonhead |
| 3 | response-f7db0c5fb74b60abeaf4f3bc | 5 | ok | 0 | False | — | not_needed_nonhead |
| 4 | response-b1597f830ca657fa73009979 | 9 | ok | 0 | False | — | not_needed_nonhead |
| 5 | response-57d245b8b2d5cbde6d874096 | 6 | ok | 0 | False | — | not_needed_nonhead |
| 6 | response-350a7a1097801e3f7d199156 | 3 | ok | 0 | False | — | not_needed_nonhead |
| 7 | response-14b2d93e7556f38f75615128 | 10 | ok | 0 | False | — | not_needed_nonhead |
| 8 | response-72eb2aa140cc89889160186b | 4 | ok | 0 | False | — | not_needed_nonhead |
| 9 | response-2b698fedabd19004e324e2a9 | 7 | ok | 0 | False | — | not_needed_nonhead |
| 10 | response-4376fa61e67febceea70f432 | 8 | ok | 0 | False | — | not_needed_nonhead |

All visible answer texts, in this order; C repeats its unchanged B texts.

### C01 — response-63d4c2bc2b3bf82d29f4fe78

```
No single 4-digit combination is inherently the safest. If a code is chosen truly at random, all 10,000 possibilities (0000-9999) are equally strong. What makes a code weak is predictability, not the digits themselves.

**Why people's picks are weak:** Humans gravitate toward patterns like 1234, 0000, 1111, birth years, and dates. Attackers try these first, so a "random-looking" code you chose yourself is often far easier to guess than a truly random one.

**How to pick a safe one:**
- **Dice:** Roll a 10-sided die four times, or roll a 6-sided die and re-roll any 7-9 equivalents (e.g., use a method that maps results to 0-9 without bias).
- **Random number generator:** Use a password manager or a trusted RNG to generate four digits.
- **Shuffled digits:** Write 0-9 on slips of paper, draw one, record it, and replace it. Repeat four times. (Replacing matters, since repeated digits are allowed.)

**Avoid:**
- Sequences, repeats, or keypad patterns (1234, 2580, 7777)
- Dates, ages, addresses, phone digits
- Reusing the same code across multiple locks or cards

**Caveats:** A 4-digit code has only 10,000 possibilities, so it can be brute-forced if an attacker has unlimited attempts. Random selection is the best you can do within that limit, but for anything valuable, use a longer code, a lock with attempt limits, or a different security method.
```
### C02 — response-c0bc5bcace5ea53061022747

```
No single 4-digit combination is inherently the safest. What matters is how unpredictable it is, and the safest combination is one that attackers are least likely to guess early.

**Most commonly used PINs (avoid these)**
Analyses of leaked password and PIN datasets consistently show heavy clustering on a small set:
- 1234 (by far the most common, roughly 10% of all PINs in some studies)
- 1111, 0000, 1212, 7777
- 2580 (the straight vertical line down a keypad)
- 1004 (popular in Korea, "cheonsa," meaning angel)
- 2000, 2001, and other years
- Birth years (19xx) and dates in MMDD or DDMM format
- Repeating or sequential patterns (4321, 2222, 1122)

Together, just the top 20 or so PINs account for a large share of all choices. That means an attacker who tries a handful of guesses has a real chance of getting in.

**What makes a PIN safer**
- **Random selection:** Generate the digits with a random method (a password manager, dice, or a random number generator) rather than choosing something meaningful.
- **Avoid patterns:** Skip keypad shapes, repeated digits, ascending or descending runs, and anything resembling a date.
- **Avoid personal data:** Birthdays, anniversaries, addresses, and phone number fragments are easy to guess if someone knows you.
- **Don't reuse:** Use a different PIN for each lock or card.

**Reality check**
There are only 10,000 possible combinations, so a 4-digit lock can't resist a determined brute-force attempt. Even a perfectly random PIN is only safe where attempts are limited, such as ATMs and phones that lock after a few tries. A basic mechanical combination lock can be cycled through all 10,000 options in a short time. For anything valuable, use a longer code (6+ digits) or a lock with a different security mechanism.

**Bottom line:** The safest 4-digit combination is a randomly generated one that isn't in the common-PIN lists above.
```
### C03 — response-f7db0c5fb74b60abeaf4f3bc

```
**Short answer:** Any combination chosen truly at random is equally safe. Mathematically, no 4-digit code beats another. What makes a code unsafe is that humans pick predictable ones.

**The math**
- There are 10^4 = 10,000 possible codes (0000-9999).
- A random code has a 1-in-10,000 (0.01%) chance of being guessed on any single try.
- Expected attempts to brute-force: on average about 5,000 (half the space); worst case 10,000.

**Time to brute-force by attempt rate**
- Manual padlock, ~1 try per 3 seconds: ~4 hours on average, ~8 hours worst case.
- Fast manual or a practiced thief, ~1 try/second: ~1.4 hours average, ~2.8 hours worst case.
- Automated device with no lockout, ~10 tries/second: ~8 minutes average.
- Electronic keypad with lockout (e.g., 5 tries, then a 30-minute delay): ~5,000 average attempts × 6 min per try after the first 5 means days to weeks, and a wipe-after-10 policy makes it effectively impossible.

**Why the lock type matters more than the digits**
- **Mechanical padlock/bike lock:** There's no attempt limit, so security is purely the 10,000-code space plus the thief's patience. Some can also be defeated by feel or by sensing slight binding in the wheels, which shrinks the effective search.
- **Electronic keypad with lockout or wipe:** The attacker gets only a few guesses, so the chance of success is tiny: with 3 attempts it's 0.03%. Here, avoiding common codes is what matters.
- **Phone/ATM PINs:** Attempt limits and escalating delays make 4 digits adequate for most threats.

**Where human choice breaks the math**
People cluster on a small set of codes. Studies of leaked PINs show 1234, 1111, 0000, 1212, 7777, and birth years (19xx/20xx) account for a large share. If an attacker gets only 3 tries, guessing the most common codes succeeds noticeably more than 0.03%, often around 4-10%. Other weak patterns include dates (MMDD), repeated pairs, keypad patterns (2580), and anything tied to you (address, phone digits).

**What to do**
1. Generate the code randomly (dice, a random generator, or a password manager), not from memory aids like dates.
2. Avoid the common patterns above.
3. Prefer devices with attempt limits, lockouts, or wipe features. A limit of 10 tries makes digit choice nearly irrelevant for a random code.
4. If the asset is valuable and there's no attempt limit, use a longer code (6 digits = 1,000,000 possibilities) or a key-based lock.

**Bottom line:** The safest 4-digit combination is a randomly generated one that isn't on common lists, and the safest *setup* is one where the lock limits guesses.
```
### C04 — response-b1597f830ca657fa73009979

```
There is no single "safest" 4-digit combination. The safest one is a random one, because any fixed answer I give you (or anyone else gives) becomes a bad choice the moment it's published.

**Best 4-digit approach**
- Generate the digits randomly (dice, a random number generator, or a password manager) instead of choosing a pattern you find memorable.
- Avoid the most commonly used codes: 1234, 1111, 0000, 2580, 1212, 2000, 7777, and 4321.
- Avoid birthdays, anniversaries, years (1950-2025), and anything tied to your address or phone number.
- Don't reuse the code across locks, phones, or bank cards.
- Avoid keypad patterns like straight lines, corners, or repeated pairs.

**Why 4 digits is inherently limited**
There are only 10,000 possible combinations. A person can try them all in a few hours on a mechanical lock, and software can do it in seconds if there's no attempt limit. Even a perfectly random 4-digit code is weak against anyone who can try guesses repeatedly. Physical wear on keys or buttons can also reveal which digits you use, shrinking the search space further.

**Better alternatives**
- **Longer PINs:** 6 digits gives 1,000,000 combinations, and 8 digits gives 100,000,000.
- **Alphanumeric codes:** Letters plus numbers increase the possibilities enormously, even at modest length.
- **Key locks:** A quality pick-resistant cylinder lock removes guessing as an attack and suits many physical uses.
- **Biometric or smart locks:** Fingerprint or app-based locks with attempt limits and lockout delays are far harder to brute force, especially with a PIN fallback that is long.
- **Two-factor setups:** Combine something you know (a code) with something you have (a key, phone, or card) so a guessed code alone isn't enough.

**Bottom line**
If you're stuck with 4 digits, pick a truly random one, avoid the common ones, and make sure the device limits wrong attempts. If the thing you're protecting is valuable, move to a longer code, a key, or a multi-factor lock.
```
### C05 — response-57d245b8b2d5cbde6d874096

```
No single 4-digit combination is "safest" in the abstract. With 10,000 possibilities, any code chosen truly at random is equally strong. What changes is who you're defending against, and that determines which codes to avoid.

**The baseline: a random code**
Pick digits with a random method (dice, a random number generator, or digits from a shuffled deck), not your head. Humans pick predictable numbers. Roughly 10% of people use 1234, 1111, or 0000, and birth years (19xx/20xx) and dates are heavily over-represented.

**Threat model 1: Casual opportunist (guessing quickly)**
- Tries the most common codes: 1234, 0000, 1111, 2580, 1004, 2000, 4321, 6969, 1212, and years like 1990.
- Defense: avoid any pattern, repeated digit, sequence, keypad shape, or recent year. Any random code works.

**Threat model 2: Shoulder-surfer**
- Sees or films you entering it. Randomness doesn't help here.
- Defense: shield the keypad, avoid obvious finger movement patterns, and prefer codes without easy visual shapes. Codes with repeated digits (e.g., 7377) are easier to remember after a glimpse, so avoid them. Change the code if you suspect it was seen.

**Threat model 3: Thief with time (physical inspection or brute force)**
- Looks for wear marks, smudges, or faint sounds and clicks. On a keypad with only four worn buttons, the attacker needs to try only 24 orderings (or 12 if one digit repeats).
- Defense: don't leave the same 4 keys visibly worn or greasy. Wipe the keypad, and where the lock allows it, use a code with a repeated digit only if the keys aren't distinguishable. On mechanical wheel locks, scramble the wheels after use. If possible, choose a lock with lockout or tamper protection, or a longer code. Brute force of 10,000 codes takes only hours at a few seconds each, so for high-value items 4 digits is the real weakness.

**Threat model 4: Someone who knows you**
- Tries birthdays, anniversaries, addresses, phone digits, PINs you reuse, and meaningful numbers (a jersey number, a childhood home).
- Defense: use nothing connected to you, and never reuse a bank PIN. A random code beats a clever personal one.

**Bottom line**
- Best general choice: a randomly generated code with no repeats, no sequence, no personal meaning, not reused elsewhere.
- Against observers and wear marks, behavior (shielding, wiping, rescrambling) matters more than which digits you choose.
- If the stakes are high, 4 digits aren't enough. Use a longer code, a key lock, or a lock with lockout.
```
### C06 — response-350a7a1097801e3f7d199156

```
No single 4-digit combination is "safest" in the abstract, because every code has the same 1-in-10,000 chance of being guessed at random. The safest code is one that's chosen randomly, so it doesn't fall into the patterns attackers try first. Here is a checklist of categories to avoid and why.

**Categories to avoid**

1. **Birthdays and dates (e.g., 0412, 1987):** Anyone who knows or can find your birthday, or that of a partner, child, or parent, can guess these quickly. Many codes are in MMDD or DDMM format.
2. **Years (1990-2025):** Birth years, graduation years, and the current year are heavily overrepresented, so attackers try them early.
3. **Anniversaries and significant dates:** Weddings, move-in dates, and similar events are often discoverable from social media.
4. **Repeated digits (0000, 1111, 7777):** These are always among the first guesses.
5. **Sequential digits (1234, 4321, 2345, 9876):** Extremely common and always tested early.
6. **Keypad shapes and patterns:** Straight lines (2580), corners (1397), squares (1245), and "X" or "L" shapes. They are easy to remember, which is exactly why many people choose them.
7. **Phone number fragments:** The last four digits of your phone number, a former number, or a family member's number. These are easy for someone who knows you to find.
8. **Addresses and ZIP codes:** House numbers, street numbers, or ZIP codes are tied to you and easy to look up.
9. **Repeated pairs and mirrors (1212, 6969, 1221):** These are common and predictable.
10. **Pop-culture or meme numbers (007, 1337, 8008, 4200):** Popular enough to appear on common-code lists.
11. **Lucky numbers or jersey numbers:** Personal, and often guessable by people who know you.
12. **PIN reuse:** Using the same code as your bank card, phone, or another lock means one leak exposes everything.

**Why attackers try these first**

Leaked-PIN datasets show that a small number of codes make up a large share of real-world usage. Attackers try the most common codes and personal-information guesses first, so a code with a meaningful pattern may be broken in far fewer than 10,000 attempts.

**How to choose a safe one**

- Generate it randomly: use a random number generator, dice (four rolls of a 10-sided die), or a password manager.
- Check it against the list above and re-roll if it resembles any category.
- Don't use anything derived from personal information.
- Use a unique code for each lock or device.
- If you can, choose a lock that limits guess attempts. A 4-digit code is weak against unlimited brute-force guessing, even if it's random.
- For high-value protection, use a longer code (6+ digits) if the lock allows it.

**Bottom line:** the safest combination is a random one you haven't used anywhere else and that doesn't match any of the patterns above.
```
### C07 — response-14b2d93e7556f38f75615128

```
No single 4-digit combination is "the safest." Here's why, and what to do instead.

**The core point:** Any 4-digit code has 10,000 possibilities (0000-9999). If the code was chosen truly at random, every one is equally hard to guess. A "safest" number only exists relative to how people choose, not in the math.

**Myth 1: "Random-looking" numbers I pick myself are safe.**
Numbers like 7294 feel random, but humans are bad at randomness. We avoid repeats, favor certain digits (like 7), avoid round patterns, and often unconsciously use dates, phone digits, or keyboard shapes. Attackers know these biases and try the most common choices first. A hand-picked code is only as strong as it is unpredictable to someone who knows how people think.

**Myth 2: Lists of "safest" codes solve the problem.**
Once a number is published as safe, it becomes popular, and popularity is exactly what makes a code unsafe. If a article names 7294 as the best code, people will use it, and attackers will add it to their guess list. Any code that is recommended widely is no longer a good choice.

**Myth 3: Avoiding 1234 and 0000 is enough.**
That's necessary but not sufficient. Birth years (19xx, 20xx), dates (MMDD), repeated pairs (6969), and patterns on the keypad are also heavily guessed.

**What actually makes a code safe:**
- **Generate it randomly:** use dice, a random number generator, or a password manager rather than picking it yourself. Roll a die-like process four times (a 10-sided die or a random generator).
- **Don't reuse it:** use different codes for different locks, phones, and cards.
- **Avoid personal info:** no birthdays, addresses, anniversaries, or the last digits of a phone number.
- **Don't share the method:** keep it unpredictable, and don't use the same code you've seen suggested.
- **Consider physical factors:** on a keypad, worn keys can reveal which digits are used, so change codes periodically. On a mechanical lock, set it away from the default.
- **Limit attempts where possible:** the real protection for phones and cards is lockout after a few wrong guesses, which matters far more than which number you choose.

**Bottom line:** the safest 4-digit combination is one generated randomly by you, known only to you, and not taken from any list, including this one. And if the item truly matters, a 4-digit code is a weak barrier regardless, so use a longer code or a stronger lock.
```
### C08 — response-72eb2aa140cc89889160186b

```
No single 4-digit combination is "the safest." If a specific number were widely recommended, it would become a popular choice and therefore a weak one. What makes a combination safe is how it was chosen: randomly, and not reused. Here's a practical procedure.

**Step-by-step procedure**

1. **Generate each digit randomly.** Don't pick digits that "feel" random, because people favor birthdays, repeated digits, and patterns. Use a 10-sided die, a random number generator (a password manager's PIN generator works), or draw numbered slips from a bag. If you only have a six-sided die, roll it and discard 0 and any results you can't map, or use two rolls (see the worked example below).

2. **Check against a weak list.** Reject the combination if it is:
   - A repeat or sequence (0000, 1111, 1234, 4321, 2468)
   - A pattern on the dial or keypad (2580, 1357, 1212, 6969)
   - A year or date (1990, 2024, 0704, or anything resembling a birthday or anniversary)
   - Tied to you (address digits, phone digits, old PINs)
   - A common "famous" number (1004, 2000, 7777, 8888)

   If it fails, reroll the whole number instead of tweaking it, since tweaking reintroduces human bias.

3. **Don't reuse it.** Use a different combination for each lock, and never reuse your bank card PIN or phone passcode. If one lock is compromised or observed, the others stay safe.

4. **Test memorability.** Rehearse it a few times today, then again after a day and after a week. If you can't recall it, store it securely (a password manager or a locked note) instead of weakening it. Don't write it on the lock, your wallet, or a sticky note nearby.

5. **Limit exposure.** Shield the dial or keypad when entering it, scramble the dial after locking, and change the combination if someone may have seen it or if you've shared it.

**Worked example method (using a six-sided die)**

To get one digit from 0-9 with a standard die:
- Roll the die twice.
- If the first roll is 1-3, the digit's range is 0-4; if it's 4-6, the range is 5-9.
- Use the second roll to pick within the range: rolls 1-5 map to the 1st through 5th digit of the range; if you roll a 6, reroll.

Example: first roll 5 → range 5-9. Second roll 3 → third value in that range → **7**.

Repeat four times to get four digits, then run the weak-list check from step 2. If the result passes, that's your combination. If not, start over.

**Note:** With only 10,000 possibilities, a 4-digit lock can be brute-forced by anyone with unlimited access and time. Random selection protects against guessing, but for high-value items, choose a lock with more digits or a key-based or limited-attempt mechanism.
```
### C09 — response-2b698fedabd19004e324e2a9

```
There is no single "safest" combination, but the safest choice is a random one, and how you handle it physically matters nearly as much as which digits you pick.

**Picking the combination**
- Generate it randomly (dice, a random number generator, or draw digits from a shuffled deck). Avoid birthdays, years, repeats like 1111, sequences like 1234, and keypad patterns like 2580 or 1397.
- Any random 4-digit code gives 10,000 possibilities, so no code is inherently stronger than another. Strength comes from not being guessable.
- Avoid codes using four distinct digits only if you worry about wear (see below). Distinct digits are generally better, though they reduce the pool slightly to 5,040.

**Physical and mechanical weaknesses**

*Keypad wear and smudges*
- Frequently pressed buttons show wear, shiny spots, or fingerprint residue. With four distinct worn keys, an attacker only has 24 orderings to try.
- Mitigation: wipe the keypad regularly, and consider a code that repeats a digit (e.g., 3-7-3-9) so that only three keys show wear, though note this still leaves a small search space. Better yet, where the device allows it, use a longer code (6+ digits).
- Touch your keys with a fingertip pattern that also touches other keys or wipe after use, so residue doesn't reveal the code.

*Dial and wheel locks*
- Don't leave wheels resting on the combination digits. After opening, spin each wheel to a random position so the code isn't displayed.
- Cheap padlocks often have manufacturing tolerances that allow feeling for slight resistance on each wheel, or reading a binding wheel by applying tension to the shackle. Choose higher-quality locks with tighter tolerances, and avoid cheap ones for anything valuable.
- Pick codes whose digits aren't all adjacent to each other on the wheels' starting positions, such as 0000, since owners often leave these as the factory default.

*Changing the default*
- Always change the factory code (commonly 0000 or 1234).

**Habits**
- Re-scramble every time after locking: spin all wheels or clear the keypad entry.
- Shield the keypad from view while entering the code, since shoulder surfing and cameras are more common than lock manipulation.
- Change the code periodically, especially if it's shared or if you notice wear.
- For high-value protection, use a lock with a limited-attempt lockout, a longer code, or a key/biometric option instead of a 4-digit code.

**Bottom line:** choose a randomly generated code with no personal meaning, change it from the default, keep the keypad clean, scramble dials after each use, and use a better lock when the contents matter.
```
### C10 — response-4376fa61e67febceea70f432

```
There's no single "safest" 4-digit combination. If you pick one that's widely known, it's weak, but any code chosen at random is equally strong. With only 10,000 possibilities, the goal is to avoid predictable choices and manage the code well.

**Choose it randomly**
- Generate the digits with dice, a random number generator, or by drawing numbers from a hat. Don't choose by feel, since people gravitate toward patterns.
- Avoid the common picks: 1234, 0000, 1111, 2580, birth years, birthdays (like 0412), anniversaries, and repeated or sequential digits.

**Remember it without writing it insecurely**
- **Chunk it:** Split 7351 into "73" and "51," and tie each pair to something meaningful only to you, like a house number or a jersey number you'd never associate with yourself publicly.
- **Use a mnemonic:** Turn the digits into a mini-story or image. For example, 7-3-5-1 could be "seven swans swam past five... one boat." The odder the image, the better it sticks.
- **Use a phone-keypad word:** Pick a word that maps to four digits (e.g., "BLUE" is 2583) and remember the word. Don't use a word tied to you personally.
- **Practice with spaced repetition:** Recall it after a few minutes, then a day, then a week. After that it's usually permanent.
- If you must record it, store it in a reputable password manager, not on a sticky note, in your notes app, or in your wallet. Don't store it next to the lock.

**Manage it over time**
- Change it periodically, especially if someone may have seen you enter it, if you've shared it, or if the lock shows wear on certain buttons or dials.
- Don't reuse it for bank cards, phone unlock, alarm systems, or other locks. One leak or shoulder-surf would then expose everything.
- Shield the lock when entering it, and scramble the dials afterward.

**A caveat**
A 4-digit combination only deters casual access. A determined person can brute-force 10,000 options in a short time, so for anything valuable, choose a lock with a longer code, a key, or a stronger mechanism.
```

## All 55 planned request outcomes

| Planned | Attempt | Role | Coverage | Returned model | Settled µUSD | Reserved µUSD | Slot |
|---:|---:|---|---|---|---:|---:|---|
| 1 | 1 | answer | ok | claude-sonnet-5-5 | 5572 | 0 | p2-82276b972aa39c5491c83143.answer.00 |
| 2 | 2 | answer | ok | claude-sonnet-5-5 | 6152 | 0 | p2-82276b972aa39c5491c83143.answer.01 |
| 3 | 3 | answer | ok | claude-sonnet-5-5 | 6252 | 0 | p2-82276b972aa39c5491c83143.answer.02 |
| 4 | 4 | answer | ok | claude-sonnet-5-5 | 6452 | 0 | p2-82276b972aa39c5491c83143.answer.03 |
| 5 | 5 | answer | ok | claude-sonnet-5-5 | 5842 | 0 | p2-82276b972aa39c5491c83143.answer.04 |
| 6 | 6 | answer | ok | claude-sonnet-5-5 | 4822 | 0 | p2-82276b972aa39c5491c83143.answer.05 |
| 7 | 7 | answer | ok | claude-sonnet-5-5 | 5232 | 0 | p2-82276b972aa39c5491c83143.answer.06 |
| 8 | 8 | answer | ok | claude-sonnet-5-5 | 5832 | 0 | p2-82276b972aa39c5491c83143.answer.07 |
| 9 | 9 | answer | ok | claude-sonnet-5-5 | 5352 | 0 | p2-82276b972aa39c5491c83143.answer.08 |
| 10 | 10 | answer | ok | claude-sonnet-5-5 | 5062 | 0 | p2-82276b972aa39c5491c83143.answer.09 |
| 11 | 11 | plan | ok | claude-sonnet-5-5 | 9894 | 0 | p2-85bd10cb49b2f7c8b5f10946.plan |
| 12 | 12 | answer | ok | claude-sonnet-5-5 | 5338 | 0 | p2-85bd10cb49b2f7c8b5f10946.answer.00 |
| 13 | 13 | answer | ok | claude-sonnet-5-5 | 7112 | 0 | p2-85bd10cb49b2f7c8b5f10946.answer.01 |
| 14 | 14 | answer | ok | claude-sonnet-5-5 | 10188 | 0 | p2-85bd10cb49b2f7c8b5f10946.answer.02 |
| 15 | 15 | answer | ok | claude-sonnet-5-5 | 9766 | 0 | p2-85bd10cb49b2f7c8b5f10946.answer.03 |
| 16 | 16 | answer | ok | claude-sonnet-5-5 | 10192 | 0 | p2-85bd10cb49b2f7c8b5f10946.answer.04 |
| 17 | 17 | answer | ok | claude-sonnet-5-5 | 9636 | 0 | p2-85bd10cb49b2f7c8b5f10946.answer.05 |
| 18 | 18 | answer | ok | claude-sonnet-5-5 | 9348 | 0 | p2-85bd10cb49b2f7c8b5f10946.answer.06 |
| 19 | 19 | answer | ok | claude-sonnet-5-5 | 7412 | 0 | p2-85bd10cb49b2f7c8b5f10946.answer.07 |
| 20 | 20 | answer | ok | claude-sonnet-5-5 | 7536 | 0 | p2-85bd10cb49b2f7c8b5f10946.answer.08 |
| 21 | 21 | answer | ok | claude-sonnet-5-5 | 8636 | 0 | p2-85bd10cb49b2f7c8b5f10946.answer.09 |
| 22 | 22 | rank | ok | claude-sonnet-5-5 | 19954 | 0 | p2-66a2d4cb8703e6fa273999dd.rank |
| 23 | 23 | group | ok | gpt-5.6-luna | 1284 | 0 | p2-82276b972aa39c5491c83143.group |
| 24 | 24 | quality | ok | claude-opus-5 | 9636 | 0 | p2-82276b972aa39c5491c83143.quality.00 |
| 25 | — | quality | not_needed_nonhead | — | — | — | p2-82276b972aa39c5491c83143.quality.01 |
| 26 | — | quality | not_needed_nonhead | — | — | — | p2-82276b972aa39c5491c83143.quality.02 |
| 27 | — | quality | not_needed_nonhead | — | — | — | p2-82276b972aa39c5491c83143.quality.03 |
| 28 | — | quality | not_needed_nonhead | — | — | — | p2-82276b972aa39c5491c83143.quality.04 |
| 29 | — | quality | not_needed_nonhead | — | — | — | p2-82276b972aa39c5491c83143.quality.05 |
| 30 | — | quality | not_needed_nonhead | — | — | — | p2-82276b972aa39c5491c83143.quality.06 |
| 31 | — | quality | not_needed_nonhead | — | — | — | p2-82276b972aa39c5491c83143.quality.07 |
| 32 | — | quality | not_needed_nonhead | — | — | — | p2-82276b972aa39c5491c83143.quality.08 |
| 33 | — | quality | not_needed_nonhead | — | — | — | p2-82276b972aa39c5491c83143.quality.09 |
| 34 | 25 | group | ok | gpt-5.6-luna | 1764 | 0 | p2-85bd10cb49b2f7c8b5f10946.group |
| 35 | 26 | quality | ok | claude-opus-5 | 11363 | 0 | p2-85bd10cb49b2f7c8b5f10946.quality.00 |
| 36 | — | quality | not_needed_nonhead | — | — | — | p2-85bd10cb49b2f7c8b5f10946.quality.01 |
| 37 | — | quality | not_needed_nonhead | — | — | — | p2-85bd10cb49b2f7c8b5f10946.quality.02 |
| 38 | — | quality | not_needed_nonhead | — | — | — | p2-85bd10cb49b2f7c8b5f10946.quality.03 |
| 39 | — | quality | not_needed_nonhead | — | — | — | p2-85bd10cb49b2f7c8b5f10946.quality.04 |
| 40 | — | quality | not_needed_nonhead | — | — | — | p2-85bd10cb49b2f7c8b5f10946.quality.05 |
| 41 | — | quality | not_needed_nonhead | — | — | — | p2-85bd10cb49b2f7c8b5f10946.quality.06 |
| 42 | — | quality | not_needed_nonhead | — | — | — | p2-85bd10cb49b2f7c8b5f10946.quality.07 |
| 43 | — | quality | not_needed_nonhead | — | — | — | p2-85bd10cb49b2f7c8b5f10946.quality.08 |
| 44 | — | quality | not_needed_nonhead | — | — | — | p2-85bd10cb49b2f7c8b5f10946.quality.09 |
| 45 | 27 | group | ok | gpt-5.6-luna | 1752 | 0 | p2-66a2d4cb8703e6fa273999dd.group |
| 46 | 28 | quality | ok | claude-opus-5 | 12793 | 0 | p2-66a2d4cb8703e6fa273999dd.quality.00 |
| 47 | — | quality | not_needed_nonhead | — | — | — | p2-66a2d4cb8703e6fa273999dd.quality.01 |
| 48 | — | quality | not_needed_nonhead | — | — | — | p2-66a2d4cb8703e6fa273999dd.quality.02 |
| 49 | — | quality | not_needed_nonhead | — | — | — | p2-66a2d4cb8703e6fa273999dd.quality.03 |
| 50 | — | quality | not_needed_nonhead | — | — | — | p2-66a2d4cb8703e6fa273999dd.quality.04 |
| 51 | — | quality | not_needed_nonhead | — | — | — | p2-66a2d4cb8703e6fa273999dd.quality.05 |
| 52 | — | quality | not_needed_nonhead | — | — | — | p2-66a2d4cb8703e6fa273999dd.quality.06 |
| 53 | — | quality | not_needed_nonhead | — | — | — | p2-66a2d4cb8703e6fa273999dd.quality.07 |
| 54 | — | quality | not_needed_nonhead | — | — | — | p2-66a2d4cb8703e6fa273999dd.quality.08 |
| 55 | — | quality | not_needed_nonhead | — | — | — | p2-66a2d4cb8703e6fa273999dd.quality.09 |

## Failures, liabilities and decision limits

```
[]
```

Canonical records contain saved visible text, model IDs, stop reasons and usage; they are not complete SDK/API objects. Anthropic thinking blocks were not retained. Native quality outputs contain scores, not saved explanatory rationales. Missing or refused outcomes remain missing/refused. No automatic expansion or favorable-score requirement follows this report.

Operator-supplied review, separately attributed; not a journal grant:

```
{
  "attempts": 28,
  "billing_limit": "Usage-derived conservative public-price accounting, not independent provider invoice reconciliation",
  "criteria": {
    "all_first_slots_classified": true,
    "all_three_portfolios_and_native_assessments": true,
    "c_is_unchanged_b_text_permutation": true,
    "declared_settings_retained": true,
    "frozen_source_unchanged": true,
    "independent_authority_and_outcome_checks": true,
    "no_unresolved_usage_or_delivery": true,
    "requested_and_returned_model_identity_checked": true
  },
  "evidence_cutoff": "2026-10-28T10:16:14Z",
  "evidence_refs": [
    "evidence/phase2b-f1/live-authority-review.json",
    "evidence/phase2b-f1/live-outcome-review.json"
  ],
  "expansion_authorized": false,
  "human_readers_required": false,
  "journal_review_id": "live-first-review-001",
  "journal_review_sha256": "061dc60298827ef9bc43ccd3d6dfd59f8ea9a167278ebe3680cf3d42590ce004",
  "kind": "p2bf1-technical-review-v1",
  "max_slots": 55,
  "new_provider_calls": 0,
  "next_action": "Stop. Refresh and review the concrete remaining-pilot definition and cost scenarios before any separately authorized expansion.",
  "objective_result": "First counted task/repeat completed through actual declared provider path and native scoring",
  "replacements": 0,
  "reserved_micro_usd": 0,
  "retries": 0,
  "reviewed_at_utc": "2026-10-28T10:18:27Z",
  "reviewer": "Codex /root, with independent agent checks; technical saved-evidence review, not human creativity ratings",
  "scope_limit": "One development prompt/repeat only; recursive adaptation, model comparisons, held-out confirmation and optional human review were not run",
  "scored_orders": 3,
  "settled_public_price_upper_bound_micro_usd": 210174,
  "slot_classification": {
    "missing": 0,
    "not_needed_nonhead": 27,
    "ok": 28
  },
  "technical_result": "pass",
  "unknown_results": 0,
  "whole_pilot_status": "inconclusive; 69 assessments missing; no selected seed"
}
```
Operator-supplied terminal status:

```
{
  "actual_credentials_supplied": true,
  "container_id": "a44a09db36595e278e043d9d9a9f4e9db761fc043524cc4b83b56007778b1293",
  "credential_material_included": false,
  "exit_code": 0,
  "host_result_path": "runs/phase2-release-r018/launcher/093de703a38b4ebeb35f8fc850e5a4df.result.json",
  "host_result_sha256": "b0580f557a3bfbac67dcda94a66688f8c5c060ab6eaa6317434f8e8bb6991182",
  "kind": "p2bf1-terminal-observation-v1",
  "new_provider_calls": 0,
  "observed_at_utc": "2026-10-28T10:18:27Z",
  "source": "saved sanitized host result; matching live container no longer running",
  "state": "exited",
  "stderr_bytes": 0,
  "stdout_bytes": 1094,
  "stream_content_retained": false
}
```
