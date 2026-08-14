FROM python:3.12-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLBACKEND=Agg \
    OPENBLAS_NUM_THREADS=1 \
    OMP_NUM_THREADS=1

WORKDIR /opt/riskfolio-src
COPY . .
RUN python -m pip install --no-cache-dir --upgrade "pip==26.1.1" \
    && python -m pip install --no-cache-dir "pytest==9.0.2" "ecos==2.0.14" \
    && python -m pip install --no-cache-dir . \
    && mkdir -p /opt/upstream-tests \
    && cp tests/test_portfolio.py tests/*.csv /opt/upstream-tests/ \
    && rm -rf /opt/riskfolio-src/riskfolio

WORKDIR /opt/upstream-tests
CMD ["python", "-c", "import riskfolio; print(riskfolio.__version__)"]
