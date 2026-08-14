FROM docker.io/library/python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=0 \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1

COPY config/robust_ml_requirements.lock /tmp/requirements.lock
RUN python -m pip install --no-cache-dir --requirement /tmp/requirements.lock

COPY containers/robust_cross_sectional_ml.py /opt/robust_cross_sectional_ml.py
COPY containers/robust_cross_sectional_ml_configurable.py /opt/robust_cross_sectional_ml_configurable.py
ENTRYPOINT ["python", "/opt/robust_cross_sectional_ml_configurable.py"]
