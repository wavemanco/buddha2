# Public source and local experiment records

The publication target is [wavemanco/buddha2](https://github.com/wavemanco/buddha2).
Only the new research working project is its source. The earlier Buddha2 folder
is outside the export, audit and publication.

The public snapshot includes original code, tests, setup files, specifications,
research notes, reports and reviewed ordinary-text evidence. Code and documentation
authored for this new research project are Apache-2.0 licensed. Copied CrPO reference code remains MIT with its
notice; other third-party terms are recorded in [Attributions](ATTRIBUTIONS.md).

The following remain local:

- Credential bindings, writer locks, caches, raw stdout/stderr and other logs.
- ZIP and Inspect `.eval` archives, installed environments and runtime binaries.
- Cached full papers, copied model/dataset cards and the supplied conversation.
- Direct MuCE human-response inspection/disagreement packets.

These are publication exclusions, not deletions from the research project.
Reports and manifests preserve the historical results, identities and relevant
source URLs. Some historical relative links therefore refer to local-only
artifacts. A public clone does not include every input needed by a frozen local
launcher, its accepted provenance packet, or its exact pinned runtime image.

The existing local Git history contains private artifact paths and remains
local. Publication uses a separate clean snapshot and a normal push to the empty
repository, preserving the local history and files. Each publication records
the reviewed export's file hashes and source commit; later publications build
on the public branch without rewriting it.

Before exporting, names are filtered before metadata/content access, eligible
ordinary text is checked for credential patterns, and third-party raw captures
are separated from original reports. No secret scan proves absence; the export
uses an explicit reviewed allowlist as well. Large unreviewed archives are not
silently moved to Git LFS or releases.
