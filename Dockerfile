FROM python:3.12-slim-bookworm@sha256:57d96f71de145a98e7ceca18ee4ade77bba4103a33a72dfaea026b23625c6bf0

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONNOUSERSITE=1 \
    HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
    TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=1

COPY requirements-build.lock requirements.lock /opt/locks/
RUN python -m pip install --no-cache-dir --no-deps --require-hashes -r /opt/locks/requirements-build.lock \
    && python -m pip install --no-cache-dir --no-deps --no-build-isolation --require-hashes -r /opt/locks/requirements.lock \
    && python -m pip check

WORKDIR /workspace
ENV PYTHONPATH=/workspace/src:/workspace/.upstream/harness2 \
    NOVELTYBENCH_ROOT=/workspace/.upstream/novelty-bench \
    BUDDHA2_NB_UPSTREAM=/workspace/.upstream/novelty-bench \
    HARNESS2_ROOT=/workspace/.upstream/harness2 \
    BUDDHA2_OUTPUT_ROOT=/results BUDDHA2_TEST_OUTPUT_ROOT=/results/acceptance \
    BUDDHA2_OFFLINE=1 TMPDIR=/tmp
ENTRYPOINT ["python", "-B", "-m", "buddha2"]
