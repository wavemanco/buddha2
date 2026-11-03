FROM oven/bun:1.3.11-slim@sha256:478281fdd196871c7e51ba6a820b7803a8ae97042ec86cdbc2e1c6b6626442d9 AS bun
FROM buddha2-phase0:local
COPY --from=bun /usr/local/bin/bun /usr/local/bin/bun
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates ripgrep libstdc++6 build-essential \
    && rm -rf /var/lib/apt/lists/*
COPY . /opt/phase3a-opencode
RUN cd /opt/phase3a-opencode && bun install --frozen-lockfile
ENV PHASE3A_OPENCODE=/opt/phase3a-opencode PHASE3A_BUN=/usr/local/bin/bun
WORKDIR /workspace
ENTRYPOINT ["python", "-B", "-m", "followups.phase3a_v1.cli"]
