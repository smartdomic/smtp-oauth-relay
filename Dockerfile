# Use an official Python runtime as a parent image
FROM python:3.14.8-slim-trixie@sha256:a2b82f3c48559aa0a8446d9af49826b6e2b2016f4cd2afabfe6013ec53729170

# Pinned UID/GID so host volumes and Kubernetes securityContexts can match
ARG UID=10001
ARG GID=10001

# Create an unprivileged user to run the relay
RUN groupadd --gid "${GID}" smtp-relay \
    && useradd --uid "${UID}" --gid "${GID}" --no-create-home --shell /usr/sbin/nologin smtp-relay

# Set the working directory in the container
WORKDIR /usr/src/smtp-relay/

# Install locked dependencies into /opt/venv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/opt/venv/bin:$PATH"
COPY ./pyproject.toml ./uv.lock ./
# Keep the build tool (and its bundled dependencies) out of the runtime image.
RUN --mount=from=ghcr.io/astral-sh/uv:0.13.1@sha256:4a1f3666816dafadd20ceb71eac9a7d56d7ef30279f7d64048519ab901ada336,source=/uv,target=/usr/local/bin/uv \
    uv sync --frozen --no-dev

# Dependencies are already installed; runtime needs neither pip nor its bootstrap wheel.
RUN /usr/local/bin/python -m pip uninstall --yes pip \
    && /usr/local/bin/python -c "import shutil, sysconfig; shutil.rmtree(sysconfig.get_path('stdlib') + '/ensurepip')"

# Copy the src contents into the container
COPY ./src .

# Create the default certificate mount point and hand ownership to the relay user
RUN mkdir -p certs && chown -R "${UID}:${GID}" /usr/src/smtp-relay

# Run the relay as the unprivileged user
USER ${UID}:${GID}

# Make port 8025 available to the world outside this container
EXPOSE 8025

# Run main.py when the container launches
CMD ["python", "main.py"]
