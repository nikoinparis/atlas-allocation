FROM docker.io/library/rust:1.85-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends cmake pkg-config clang libssl-dev \
    && rm -rf /var/lib/apt/lists/*

LABEL org.opencontainers.image.title="Portfolio Optimizer 2.0 Rust native test profile" \
      org.opencontainers.image.description="Pinned Rust 1.85 profile with native build prerequisites; no project source or secrets"
