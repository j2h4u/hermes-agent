ARG HERMES_BASE_IMAGE=hermes-agent:upstream-local
FROM ${HERMES_BASE_IMAGE}

ARG EXPECTED_HERMES_GIT_SHA
RUN test -n "$EXPECTED_HERMES_GIT_SHA" \
    && test -f /opt/hermes/.hermes_build_sha \
    && test "$(cat /opt/hermes/.hermes_build_sha)" = "$EXPECTED_HERMES_GIT_SHA"

ARG COMPRESR_VERSION=2.9.2
ARG COMPRESR_EXCLUDE_NEWER=2026-08-02T00:00:00Z
USER root
RUN uv_bin="$(/opt/hermes/.venv/bin/python -c 'from pm._uv import _toolchain; print(_toolchain(realize=False)[0])')" && \
    "$uv_bin" pip install \
        --python /opt/hermes/.venv/bin/python \
        --default-index https://pypi.org/simple \
        --exclude-newer "${COMPRESR_EXCLUDE_NEWER}" \
        --no-cache-dir \
        "compresr==${COMPRESR_VERSION}" && \
    rm -f /opt/hermes/.venv/.lock

# Remove/review the guarded patch when upgrading the external plugin.
COPY docker/patch_compresr_threshold.py /opt/hermes/docker/patch_compresr_threshold.py
RUN /opt/hermes/.venv/bin/python /opt/hermes/docker/patch_compresr_threshold.py && \
    /opt/hermes/.venv/bin/python /opt/hermes/docker/patch_compresr_threshold.py --verify
