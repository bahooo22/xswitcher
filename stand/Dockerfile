# golang:1.26 rather than debian:trixie-slim + golang-go: the module pins go 1.26.0 / toolchain
# go1.26.10 (measured with govulncheck: the standard-library findings clear only from 1.26.10), and
# the Go shipped in the Debian archive is older than that.
FROM golang:1.26-trixie

# Build toolchain for xswitcher (cgo + X11 bindings) and the stand's observation tools.
RUN apt-get update -qq && apt-get install -y --no-install-recommends \
    ca-certificates gcc pkg-config libx11-dev libxmu-dev \
    xvfb x11-utils x11-xkb-utils xkb-data xdotool python3 python3-evdev kbd \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /w
CMD ["bash", "/w/stand/run.sh"]
