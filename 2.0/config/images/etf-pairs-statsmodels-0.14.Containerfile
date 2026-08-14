FROM docker.io/library/python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=0 \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1

COPY config/pairs_requirements.lock /tmp/requirements.lock
RUN python -m pip install --no-cache-dir --requirement /tmp/requirements.lock

COPY containers/etf_pairs_engine.py /opt/etf_pairs_engine.py
COPY src/systematic_trader/pair_protocol.py /opt/pair_protocol.py
ENTRYPOINT ["python", "/opt/etf_pairs_engine.py"]
