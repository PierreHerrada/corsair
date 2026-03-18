FROM python:3.12-slim

# System deps: Node.js 20 (for Claude Code CLI), git, JDK, openssh
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl git default-jdk-headless openssh-client && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    npm install -g @anthropic-ai/claude-code && \
    rm -rf /var/lib/apt/lists/*

# Docker CLI (for Testcontainers via DinD sidecar)
RUN curl -fsSL https://download.docker.com/linux/static/stable/x86_64/docker-25.0.3.tgz | \
    tar xz --strip-components=1 -C /usr/local/bin docker/docker

ENV JAVA_HOME=/usr/lib/jvm/default-java
ENV PATH="${JAVA_HOME}/bin:${PATH}"

WORKDIR /app

# Non-root user (Claude Code refuses to run as root)
RUN useradd -m -s /bin/bash corsair && \
    mkdir -p /home/corsair/workspaces && \
    chown -R corsair:corsair /home/corsair

# Python deps
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Harness code
COPY config.py log_streamer.py prompt_loader.py harness.py ./

USER corsair
ENTRYPOINT ["python", "harness.py"]
