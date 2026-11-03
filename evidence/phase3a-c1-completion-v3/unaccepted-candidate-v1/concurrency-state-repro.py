"""One-request offline reproduction; not part of frozen source or a live route."""
from __future__ import annotations
import json,threading,time,uuid
from pathlib import Path
from buddha2 import phase2_am1_controls as am1
from buddha2.artifacts import digest,write_once
from followups.phase3a_c1_completion_v3 import accounting as a
from followups.phase3a_c1_completion_v3.tests.fixtures import Transport
from followups.phase3a_v1.tests.test_accounting import request,slots


def main():
    sha=digest({"case":"frozen-v3-state-concurrency-reproduction","nonce":uuid.uuid4().hex})
    journal=a.canonical_journal(sha,True)
    bindings={"source_sha256":"2"*64,"policy_sha256":digest(a.POLICY),"launcher_sha256":"4"*64}
    authority={"study_sha256":sha,"authorization_id":"concurrency-reproduction-fixture","authorized":False,
      "cap_micro_usd":a.POLICY["phase_micro_usd"],"canary_cap_micro_usd":a.POLICY["first_micro_usd"],
      "expansion_authorized":False,"control_policy_sha256":am1.CONTROL_SHA256,"billing_profile":am1.BILLING_PROFILE}
    transport=Transport()
    entered,release=threading.Event(),threading.Event()
    mock=transport._http["anthropic"]
    original=mock.handler
    def delayed(http_request):
        response=original(http_request)
        entered.set()
        if not release.wait(10): raise RuntimeError("reproduction response barrier expired")
        return response
    mock.handler=delayed
    ledger=a.Ledger(journal,study_sha256=sha,slots=slots(),authority=authority,transport=transport,bindings=bindings)
    results=[]
    def dispatch():
        try: results.append(ledger.dispatch("p3a-01.adaptive.plan.00","plan",request()))
        except BaseException as exc: results.append({"exception_type":type(exc).__name__})
    worker=threading.Thread(target=dispatch)
    try:
        worker.start()
        if not entered.wait(15): raise RuntimeError("actual SDK fixture did not enter response barrier")
        before=time.monotonic()
        transient=ledger.state()
        returned=time.monotonic()-before
        actual_events=a.events(journal)
        durable_unknown=sum(event["kind"]=="result" and event["record"]["status"]!="response" for event in actual_events)
    finally:
        release.set()
        worker.join(20)
        transport.close()
    if worker.is_alive(): raise RuntimeError("reproduction worker failed to settle")
    final=ledger.state()
    proof={"kind":"frozen-v3-state-concurrency-reproduction-v1","fixture":True,"provider_calls":0,"real_spend_micro_usd":0,
      "candidate_study_sha256":"fcfa299b8ecb4c447bb8b573148f1ddca2466beb6a290c9180622eb18685387b",
      "candidate_source_sha256":"66779bdaef1b2fd55e54997184eae71e07d2f57a50a2239c8d1e41930ae0a555",
      "fixture_journal":str(journal),"actual_mock_sdk_requests":len(transport.calls),
      "concurrent_state_return_seconds":returned,"concurrent_state_status":transient["status"],
      "concurrent_state_results":{slot:result["status"] for slot,result in transient["results"].items()},
      "concurrent_active_unsettled_intents":transient["active_unsettled_intents"],
      "concurrent_durable_unknown_results":transient["durable_unknown_results"],
      "durable_event_kinds_at_concurrent_read":[event["kind"] for event in actual_events],"durable_unknown_events_at_concurrent_read":durable_unknown,
      "final_status":final["status"],"final_result_statuses":{slot:result["status"] for slot,result in final["results"].items()},
      "final_attempts":final["attempts"],"final_known_spent_micro_usd":final["spent_micro_usd"],"final_reserved_micro_usd":final["reserved_micro_usd"],
      "confirmed_bug":transient["status"]=="blocked-unknown" and not durable_unknown and final["status"]=="ready"}
    output=Path("/results/phase3a-c1-completion-v3/verification-v1/concurrency-state-repro.json")
    write_once(output,proof)
    print(json.dumps(proof,sort_keys=True))
    if not proof["confirmed_bug"]: raise SystemExit(1)

if __name__=="__main__": main()
