FROM python:3.12-slim-bookworm@sha256:57d96f71de145a98e7ceca18ee4ade77bba4103a33a72dfaea026b23625c6bf0
COPY wheels /wheels
COPY requirements.lock /requirements.lock
RUN python -m pip install --no-index --no-deps --require-hashes --find-links /wheels -r /requirements.lock && python -m pip check && python -m pip freeze --all > /installed.txt
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/tmp/empty-home
WORKDIR /out
