# Final keyless provider preflight

This artifact checks the unchanged frozen provider launch path after the offline ten-group gate and two-part packet acceptance. It changes no production source. It starts no experiment, model, credential prompt, Transport or published allowance claim.

The external independent receipt is `evidence/phase3a-h1-integrated-v1/packet-acceptance.json`, SHA256 `31fdee4427f4e4609b82209d9d312201004fba019e32d13c68d27a235b47e32c`. The complete accepted packet is the preserved main archive/manifest **plus** its launcher-evidence companion archive/manifest and original-to-copy map. The main archive alone is insufficient. The frozen runtime validates its main packet fields; this keyless host boundary additionally validates both parts and map against the independent receipt. No archive is edited or retagged.

`provider_preflight.py --check-only` validates the fixed public bundle paths/current source and writes a sidecar. It starts no container. `--host` creates one fresh `actual-v1` namespace, reuses unchanged `verify.container_args`, and executes the helper inside the actual accepted H1 image with network none, source read-only, and only this project's `runs/phase3a-h1-integrated-v1` namespace writable. No host credentials are passed. Pinned runtime environment and actual mounts/image are checked. Inside, SDK constructors and socket/subprocess activity are blocked before unchanged `launch.preflight(study, live_grant, 'all', 'provider')`. It validates the accepted packet through the real provider-mode path without invoking `execute`, requesting keys, constructing a Transport or publishing the global claim. All five bindings and the external packet receipt SHA are retained. Bundle/source/claim stability is checked before and after, and the exact owned container is removed on exit.

After independent review of this helper's exact hash, root runs once from the project root:

```powershell
python -I -B '.\runs\phase3a-h1-integrated-v1\verification-v4\provider-preflight-v1\provider_preflight.py' --host
```

The helper sets its own public Python paths/output root before project imports. No PATH-based `pwsh` is required. Outputs are exclusive creation. Any mismatch, attempted execution, failed preflight or unproved cleanup stops the check; retain all evidence and do not automatically repeat or overwrite it. Root may request fresh masked keys only after this actual proof and independent confirmation. Root separately captures the exact PS5/PS7 PID/start identities for the accepted operator-ownership receipt when the live launcher opens; this helper neither opens that launcher nor reads process environments.

The helper is a post-packet operator artifact, not part of the immutable 356-file production source. Bind its hash and this supplemental proof in the launch record; preserve the accepted two-part packet and historical failed verification invocation unchanged. A successful preflight establishes source/authority/guard readiness, not successful live requests or recursive improvement.
