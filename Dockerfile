# camouchat-whatsapp — consumer image
#
# Builds on top of camouchat-browser-base which already has:
#   - All Firefox/Camoufox system libs
#   - Camoufox browser binary baked in
#   - xvfb, xclip, fonts
#   - camouchat-core + camouchat-browser installed
#
# Build:
#   docker build -t camouchat-whatsapp:latest .
#
# Run (use docker-compose.yml instead for full persistence setup):
#   docker run --shm-size=2gb -v whatsapp-data:/data camouchat-whatsapp:latest

FROM camouchat-browser-base:latest

# Switch to root to install packages, then drop back to app user
USER root

# ── Redirect ALL persistence to /data (the named volume mount point) ───────────
# platformdirs respects XDG env vars on Linux; pointing them under /data means
# profiles, login session, encryption keys, DB, media, and logs all survive
# docker compose down / up without re-login.
#
# XDG_CACHE_HOME also controls where Camoufox looks for its browser binary —
# the base image baked the binary at /opt/cache/camoufox.
# At runtime we copy it to /data/cache/camoufox on first boot (see entrypoint).
ENV XDG_DATA_HOME=/data/share \
    XDG_CACHE_HOME=/data/cache \
    XDG_STATE_HOME=/data/state

# ── Install camouchat-whatsapp (the platform plugin) ───────────────────────────
ARG PLUGIN_REF="camouchat-whatsapp"
RUN uv pip install --system "${PLUGIN_REF}"

# ── Copy user application code ─────────────────────────────────────────────────
# Place your bot scripts in an app/ directory next to this Dockerfile.
# The file app/main.py is the default entry point.
# Replace or extend this COPY if your structure differs.
COPY --chown=app:app app/ /home/app/app/

# ── Volume declaration ─────────────────────────────────────────────────────────
# Declare /data as the persistence volume. Profiles, cookies (login session),
# encryption keys, fingerprints, SQLite DB, and media all land here.
# Mount a named Docker volume here — never use a tmpfs or anonymous volume.
VOLUME ["/data"]

# ── Entrypoint: copy Camoufox binary from build layer on first boot ────────────
# The browser binary was baked into the base image at /opt/cache/camoufox.
# At runtime /data/cache is the volume, so the binary won't be there yet.
# This entrypoint copies it once on first container start; subsequent starts skip the copy.
COPY --chown=app:app docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

USER app
WORKDIR /home/app

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["python", "app/main.py"]

LABEL org.opencontainers.image.title="camouchat-whatsapp" \
      org.opencontainers.image.description="WhatsApp Web automation plugin for CamouChat, containerized" \
      org.opencontainers.image.source="https://github.com/CamouChat-Team/camouchat-whatsapp"
