# syntax=docker/dockerfile:1
# Headless robo-evals image. Rendering uses OSMesa (pure software OpenGL), so
# videos work on any amd64 or arm64 host without a GPU or a display.

ARG PYTHON_VERSION=3.12

FROM python:${PYTHON_VERSION}-slim-bookworm AS build
WORKDIR /src
RUN pip install --no-cache-dir build==1.3.0
COPY pyproject.toml README.md LICENSE CHANGELOG.md CITATION.cff ./
COPY src ./src
RUN python -m build --wheel --outdir /dist

FROM python:${PYTHON_VERSION}-slim-bookworm
ARG VERSION=dev
LABEL org.opencontainers.image.title="robo-evals" \
      org.opencontainers.image.description="Reproducible evaluation harness for robot manipulation policies in MuJoCo simulation." \
      org.opencontainers.image.source="https://github.com/superintelligenceco/robo-evals" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.version="${VERSION}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends libosmesa6 libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /dist/*.whl /tmp/
RUN pip install --no-cache-dir "$(ls /tmp/robo_evals-*.whl)[video,ws]" \
    && rm -f /tmp/*.whl

ENV MUJOCO_GL=osmesa \
    PYOPENGL_PLATFORM=osmesa \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp

# Mount a host directory at /out. By default, reports land in /out/results/<policy>/.
# The image runs as an unprivileged user; pass --user "$(id -u):$(id -g)" so files
# written to a mounted directory belong to you.
RUN mkdir -p /out && chmod 777 /out
WORKDIR /out
USER 65532:65532
ENTRYPOINT ["robo-evals"]
CMD ["--help"]
