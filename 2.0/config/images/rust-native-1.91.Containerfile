FROM docker.io/library/rust:1.91.1-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends cmake pkg-config clang libssl-dev \
    && rm -rf /var/lib/apt/lists/*

LABEL org.opencontainers.image.title="Portfolio Optimizer 2.0 Rust 1.91 native test profile" \
      org.opencontainers.image.description="Manifest-aligned Rust 1.91.1 profile with native prerequisites; no project source or secrets"
