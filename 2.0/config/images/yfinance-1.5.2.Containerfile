FROM docker.io/library/python:3.12-slim-bookworm

COPY config/free_data_requirements.lock /opt/portfolio-optimizer/requirements.lock

RUN python -m pip install --no-cache-dir -r /opt/portfolio-optimizer/requirements.lock

COPY scripts/container/free_etf_download.py /opt/portfolio-optimizer/free_etf_download.py

ENTRYPOINT ["python", "/opt/portfolio-optimizer/free_etf_download.py"]

LABEL org.opencontainers.image.title="Portfolio Optimizer 2.0 free ETF acquisition" \
      org.opencontainers.image.description="Isolated yfinance 1.5.2 snapshot collector; outputs remain research-only" \
      org.opencontainers.image.version="1"
