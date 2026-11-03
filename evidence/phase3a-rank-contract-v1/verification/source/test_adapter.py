"""Execute the prefrozen 76 RC1 mechanical cases; no providers or native engine."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from buddha2.artifacts import ContractError, digest, file_hash
from buddha2.phase2_contracts import make_portfolio, permute_portfolio
from buddha2.phase2_dispatch import FROZEN_PROFILES
from followups.phase3a_v1.strategy import render_strategy_request, seed_templates

from . import adapter

INVENTORY_SHA256 = "c4ccc6f2830f7122f604febfdf33028a0902e307e371aa9ad1bf75ad976dc878"
MANIFEST_SHA256 = "18c192a24fa41284aa1dba23b09981d17318712940de7c077a450f15471cc48d"
PARENT_SHA256 = "e2307d9d007495e9381fe723edacf437f998e57cf15b09d98a97c83688645408"
LABELS = [f"r{i:02d}" for i in range(1, 11)]
ORDERS = [list(range(10)), list(reversed(range(10))), [2, 0, 1, 4, 3, 6, 5, 9, 7, 8]]
FIELDS = ("answer_system", "plan_system", "rank_system")


def require(value, message):
    if not value:
        raise AssertionError(message)


def write(path, value):
    # C17's invalid scalar is preserved as its JSON escape, never repaired or UTF-8 encoded.
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=True, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


def sealed(value):
    body = {k: copy.deepcopy(v) for k, v in value.items() if k != "sha256"}
    return {**body, "sha256": digest(body)}


def synthetic_parent(strategy):
    task = {"id": "rc1-synthetic-task", "prompt": "SYNTHETIC mechanical mapping only; no semantic ranking.",
            "domain": "synthetic", "source_context": {"dataset": "synthetic", "revision": "a" * 40,
            "source_sha256": "b" * 64, "source_task_id": "rc1-synthetic-task"}}
    ids = ["response-" + digest({"synthetic_slot": i})[:24] for i in range(10)]
    literal = f"SYNTHETIC duplicate text r01 r10 {ids[0]} {ids[9]}\nExact Unicode: α."
    responses = [{"id": ids[i], "text": literal if i < 2 else f"SYNTHETIC answer {i}: {literal}",
                  "status": "ok" if i < 2 else ("ok", "refused", "empty", "truncated")[i % 4],
                  "request_id": f"rc1-parent.answer.{i:02}"} for i in range(10)]
    return make_portfolio(task, responses, method="B", repeat=1,
        model={"requested": "fixture-no-model", "returned": "fixture-no-model"},
        settings_sha256=digest({r: FROZEN_PROFILES[r] for r in ("plan", "answer", "rank")}),
        procedure_sha256=digest({"kind": "phase3a-plan-answers-v1", "strategy": strategy}),
        request_ids=["rc1-parent.plan", *[r["request_id"] for r in responses]], study_sha256="c" * 64, fixture=True)


def alternate_parent(parent):
    task = copy.deepcopy(parent["task"])
    task["id"] = "rc1-synthetic-other-parent"
    task["prompt"] = "SYNTHETIC second parent with the same aliases and unchanged answer records."
    p = parent["provenance"]
    return make_portfolio(task, parent["responses"], method="B", repeat=p["repeat"], model=p["model"],
        settings_sha256=p["settings_sha256"], procedure_sha256=p["procedure_sha256"],
        request_ids=p["request_ids"], study_sha256=p["study_sha256"], fixture=parent["fixture"])


def context(parent, case, caller="fixed-candidate"):
    return {"study_sha256": parent["provenance"]["study_sha256"], "run_id": "rc1-synthetic-run-" + case,
            "slot_id": "rc1-synthetic-" + case + "-" + caller, "caller": caller, "synthetic": True}


def text(order):
    return json.dumps({"order": order})


def reply_fixtures():
    valid, reverse = text(LABELS), text(LABELS[::-1])
    invalid = text([*LABELS[:-1], LABELS[0]])
    positive = [valid, "Here is the order.\n" + valid, "```json\n" + valid + "\n```",
        valid + " Correction: same order. " + valid, valid + valid,
        " \n\t" + json.dumps({"order": LABELS}, indent=2) + " \n",
        valid.replace('"order"', '"ord\\u0065r"').replace('"r01"', '"\\u007201"'),
        "SYNTHETIC α🙂 prefix\n" + valid, "The prose says reverse; this text is not an order. " + valid,
        "Rank 123, 456, 789. " + valid, "\n".join([valid] * 16), " " * (65_536 - len(valid)) + valid]
    def changed(value):
        return text([value, *LABELS[1:]])
    negative = [text(LABELS[:-1]), invalid, changed("foreign"), changed("R01"), changed("ｒ01"),
        changed("r01 "), changed(1), changed(True), changed(None),
        json.dumps({"order": LABELS, "extra": "not allowed"}),
        '{"order":' + json.dumps(LABELS) + ',"ord\\u0065r":' + json.dumps(LABELS) + '}',
        valid[:-1] + ",}", valid[:-1], "]" + valid, "No object supplied.", changed(float("nan")),
        "\ud800" + valid, " " * 65_537, "é" * 32_768 + valid,
        json.dumps({"order": [LABELS]}), '{"wrapper":' + valid + '}',
        "\n".join([valid] * 17), valid + reverse, valid + invalid, invalid + valid, valid + " {\"order\":"]
    return {**{f"B{i:02}": raw for i, raw in enumerate(positive, 1)},
            **{f"C{i:02}": raw for i, raw in enumerate(negative, 1)}}


def flags(derived):
    require(derived["synthetic"] is True and derived["unscored"] is True and derived["provider_calls"] == 0
            and derived["eligible_live_result"] is False, "synthetic derivation provenance missing")
    require(derived == sealed(derived), "derivation identity differs")


def derive(parent, strategy, ctx, raw):
    prepared = adapter.prepare(parent, parent["task"], strategy, ctx)
    bound = adapter.synthetic_result_binding(prepared, raw)
    derived = adapter.derive(parent, parent["task"], strategy, ctx, prepared, raw, bound)
    flags(derived)
    return prepared, bound, derived


def check_accepted(parent, strategy, ctx, raw, indices):
    before = copy.deepcopy((parent, strategy, ctx))
    prepared, _, result = derive(parent, strategy, ctx, raw)
    require(result["status"] == "accepted" and result["reason"] is None, "valid permutation rejected")
    expected_ids = [parent["responses"][i]["id"] for i in indices]
    require(result["label_order"] == [LABELS[i] for i in indices]
            and result["canonical_order"] == expected_ids, "permutation changed")
    expected = permute_portfolio(parent, expected_ids, request_id=ctx["slot_id"],
        settings_sha256=parent["provenance"]["settings_sha256"], procedure_sha256=result["procedure_sha256"])
    require(result["canonical_output"] == expected, "real canonical permutation differs")
    require(result["canonical_output"]["responses"] == [parent["responses"][i] for i in indices], "answer bytes/fields changed")
    require((parent, strategy, ctx) == before, "caller inputs mutated")
    require(prepared["mapping"]["entries"] == [{"label": LABELS[i], "canonical_id": r["id"]}
        for i, r in enumerate(parent["responses"])], "map is not generation-order bijection")
    return result


def corruption(number, parent, strategy, ctx):
    raw = text(LABELS)
    prepared, bound, _ = derive(parent, strategy, ctx, raw)
    parent, strategy, ctx, prepared, bound = copy.deepcopy((parent, strategy, ctx, prepared, bound))
    if number == 1:
        parent["responses"].pop()
    elif number == 2:
        parent["responses"][1]["id"] = parent["responses"][0]["id"]
    elif number == 3:
        parent["responses"][0]["text"] += " SYNTHETIC stale identity"
    elif number == 4:
        entries = prepared["mapping"]["entries"]
        entries[0]["canonical_id"], entries[1]["canonical_id"] = entries[1]["canonical_id"], entries[0]["canonical_id"]
        prepared["mapping"] = sealed(prepared["mapping"])
        prepared["request_binding"]["map_sha256"] = prepared["mapping"]["sha256"]
        prepared["request_binding"] = sealed(prepared["request_binding"])
        prepared = sealed(prepared)
        bound = adapter.synthetic_result_binding(prepared, raw)
    elif number == 5:
        prepared["mapping"]["sha256"] = "0" * 64
    elif number == 6:
        prepared["mapping"]["profile_sha256"] = "0" * 64
    elif number == 7:
        prepared["request"]["system"] += " SYNTHETIC unbound request alteration"
    elif number == 8:
        prepared["request_binding"]["request_sha256"] = "0" * 64
    elif number == 9:
        strategy["rank_system"] += " SYNTHETIC changed consumed strategy"
    elif number in (10, 11, 12, 13):
        key = {10: "study_sha256", 11: "run_id", 12: "slot_id", 13: "caller"}[number]
        ctx[key] = "d" * 64 if number == 10 else "native-rollout" if number == 13 else ctx[key] + "-other"
    elif number in (14, 15):
        bound["raw_reply_sha256" if number == 14 else "request_sha256"] = "0" * 64
        bound = sealed(bound)
    elif number == 16:
        parent = alternate_parent(parent)
    elif number in (17, 18):
        bound["synthetic" if number == 17 else "provider_calls"] = False if number == 17 else 1
        bound = sealed(bound)
    if number in (5, 6, 7, 8):
        prepared = sealed(prepared)
    try:
        adapter.derive(parent, parent["task"], strategy, ctx, prepared, raw, bound)
    except ContractError:
        return {"status": "ContractError_before_acceptance", "proof": "bound provenance rejected; no canonical output"}
    return {"status": "unexpected_acceptance", "proof": "integrity corruption was not rejected"}


def invariant(number, parent, strategy, case):
    ctx = context(parent, case)
    prepared, _, result = derive(parent, strategy, ctx, text(LABELS))
    if number == 1:
        legacy = render_strategy_request("rank", parent["task"], strategy, responses=parent["responses"])
        request = copy.deepcopy(prepared["request"])
        body = json.loads(request["messages"][0]["content"])
        require(body["responses"] == [{"id": label, "text": response["text"]}
            for label, response in zip(LABELS, parent["responses"], strict=True)], "wire answer text/order differs")
        for response, original in zip(body["responses"], parent["responses"], strict=True):
            response["id"] = original["id"]
        request["messages"][0]["content"] = json.dumps(body, ensure_ascii=False)
        require(request == legacy, "renderer delta exceeds response id values")
    elif number == 2:
        require(set(strategy) == set(FIELDS) and strategy == {k: seed_templates()[k] for k in FIELDS}, "seed fields differ")
        for role in ("plan", "answer", "rank"):
            request = render_strategy_request(role, parent["task"], strategy, responses=parent["responses"])
            require(request["system"] == strategy[role + "_system"], "declared strategy field not consumed")
    elif number == 3:
        edited = {**strategy, "rank_system": strategy["rank_system"] + " SYNTHETIC edit: consider supplied order carefully."}
        changed, _, child = derive(parent, edited, ctx, text(LABELS))
        require(changed["request"]["system"] == edited["rank_system"] and prepared["request"]["system"] == strategy["rank_system"],
                "rank_system edit was not consumed exactly")
        require(changed["mapping"]["profile_sha256"] == prepared["mapping"]["profile_sha256"]
                and child["procedure_sha256"] != result["procedure_sha256"], "edit froze schema or lost method identity")
        bad = adapter.derive(parent, parent["task"], edited, ctx, changed, text(LABELS[:-1]),
                             adapter.synthetic_result_binding(changed, text(LABELS[:-1])))
        require(bad["status"] == "rejected" and bad["reason"] == "invalid_ids", "strategy edit changed validation authority")
    elif number == 4:
        require(result["canonical_output"]["provenance"]["settings_sha256"] == parent["provenance"]["settings_sha256"],
                "settings identity changed")
    elif number == 5:
        other = alternate_parent(parent)
        _, _, second = derive(other, strategy, context(other, case + "-second", "native-rollout"), text(LABELS))
        require(result["procedure_sha256"] == second["procedure_sha256"]
                and result["map_sha256"] != second["map_sha256"]
                and result["procedure_sha256"] != parent["provenance"]["procedure_sha256"], "method and map identity conflated")
    elif number == 6:
        require(parent["responses"][0]["text"] == parent["responses"][1]["text"], "duplicate-text fixture missing")
        check_accepted(parent, strategy, ctx, text(LABELS[::-1]), ORDERS[1])
    elif number == 7:
        before = copy.deepcopy((parent, strategy, ctx, prepared, result))
        repeated = derive(parent, strategy, ctx, text(LABELS))
        require(repeated[0] == prepared and repeated[2] == result
                and (parent, strategy, ctx, prepared, result) == before, "saved replay differs or mutates inputs")
    elif number == 8:
        native = context(parent, case + "-native", "native-rollout")
        second, _, other = derive(parent, strategy, native, text(LABELS))
        require(prepared["request"] == second["request"] and prepared["mapping"]["entries"] == second["mapping"]["entries"]
                and result["canonical_output"]["responses"] == other["canonical_output"]["responses"], "caller contracts differ")
    return {"status": "invariant_pass", "proof": "actual renderer/canonical functions and immutable synthetic evidence checked"}


def run_inventory(input_dir: Path = Path("/inputs"), output_dir: Path = Path("/out")) -> dict:
    require(file_hash(input_dir / "manifest.json") == MANIFEST_SHA256
            and file_hash(input_dir / "fixture-inventory.json") == INVENTORY_SHA256, "prefrozen input metadata changed")
    manifest = json.loads((input_dir / "manifest.json").read_text(encoding="utf-8"))
    for name in ("saved_parent.json", "strategy.json"):
        require(file_hash(input_dir / name) == manifest["inputs"][name]["file_sha256"], "fixture input bytes changed")
    inventory = json.loads((input_dir / "fixture-inventory.json").read_text(encoding="utf-8"))["new_cases"]
    require([r["id"] for r in inventory] == [f"{g}{i:02}" for g, n in (("A", 12), ("B", 12), ("C", 26), ("D", 18), ("E", 8))
            for i in range(1, n + 1)], "frozen 76-case coverage differs")
    saved = json.loads((input_dir / "saved_parent.json").read_text(encoding="utf-8"))
    require(digest(saved) == PARENT_SHA256, "saved method-B parent identity differs")
    strategy = json.loads((input_dir / "strategy.json").read_text(encoding="utf-8"))
    parent = synthetic_parent(strategy)
    replies = reply_fixtures()
    write(output_dir / "executed-fixtures.json", {"synthetic": True, "unscored": True, "provider_calls": 0,
          "eligible_live_result": False, "inventory_sha256": INVENTORY_SHA256, "raw_replies": replies,
          "synthetic_parent": parent, "saved_parent_sha256": PARENT_SHA256, "orders": ORDERS})
    rows = []
    for case in inventory:
        identity, number = case["id"], int(case["id"][1:])
        try:
            require(tuple(LABELS) == adapter.LABELS, "wire labels differ")
            if identity.startswith("A"):
                index = number - 1
                chosen = parent if index < 6 else saved
                caller = "fixed-candidate" if index % 6 < 3 else "native-rollout"
                order = ORDERS[index % 3]
                result = check_accepted(chosen, strategy, context(chosen, identity, caller), text([LABELS[i] for i in order]), order)
                actual = {"status": result["status"], "reason": result["reason"],
                          "proof": {"canonical_output_sha256": result["canonical_output_sha256"], "synthetic": True}}
            elif identity.startswith(("B", "C")):
                _, _, result = derive(parent, strategy, context(parent, identity), replies[identity])
                if result["status"] == "accepted":
                    check_accepted(parent, strategy, context(parent, identity), replies[identity], ORDERS[0])
                else:
                    require(result["canonical_output"] is None and result["canonical_order"] is None
                            and result["label_order"] is None, "rejection produced an order/output")
                actual = {"status": result["status"], "reason": result["reason"],
                          "proof": {"raw_reply_sha256": result["raw_reply_sha256"],
                                    "candidate_count": len(result["normalization"]["candidates"]), "synthetic": True}}
            elif identity.startswith("D"):
                actual = corruption(number, parent, strategy, context(parent, identity))
            else:
                actual = invariant(number, parent, strategy, identity)
            passed = actual["status"] == case["expected"] and actual.get("reason") == case.get("reason")
        except Exception as error:
            actual = {"status": "test_error", "exception_type": type(error).__name__, "message": str(error)[:180]}
            passed = False
        rows.append({"id": identity, "case": case["case"], "expected": case["expected"],
                     "expected_reason": case.get("reason"), "actual": actual, "passed": passed})
    summary = {"passed": len(rows) == 76 and all(r["passed"] for r in rows), "case_count": len(rows),
               "provider_calls": 0, "synthetic": True, "inventory_sha256": INVENTORY_SHA256,
               "cases": rows}
    write(output_dir / "cases.json", rows)
    return summary


if __name__ == "__main__":
    report = run_inventory()
    print(json.dumps({"passed": report["passed"], "case_count": report["case_count"],
                      "failed_ids": [r["id"] for r in report["cases"] if not r["passed"]], "provider_calls": 0}))
    raise SystemExit(0 if report["passed"] else 1)
