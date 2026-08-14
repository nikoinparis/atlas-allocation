FROM docker.io/library/rust:1.55-bullseye

RUN apt-get update \
    && apt-get install -y --no-install-recommends cmake pkg-config clang libssl-dev \
    && rm -rf /var/lib/apt/lists/*

LABEL org.opencontainers.image.title="Portfolio Optimizer 2.0 legacy Rust native test profile" \
      org.opencontainers.image.description="Repository-aligned Rust 1.55 profile for pinned legacy candidates; no project source or secrets"
