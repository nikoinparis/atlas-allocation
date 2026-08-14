FROM localhost/python:3.12-bookworm-arm64

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OPENBLAS_NUM_THREADS=1 \
    OMP_NUM_THREADS=1

WORKDIR /opt/skfolio-src
COPY . .
RUN python -m pip install --no-cache-dir --upgrade "pip==26.1.1" \
    && python -m pip install --no-cache-dir . "pytest==9.1.1" "pytest-cov==7.1.0"
RUN python -c "from skfolio.datasets import load_ftse100_dataset, load_nasdaq_dataset, load_sp500_implied_vol_dataset; load_ftse100_dataset(); load_nasdaq_dataset(); load_sp500_implied_vol_dataset()"

CMD ["python", "-c", "import skfolio; print(skfolio.__version__)"]
