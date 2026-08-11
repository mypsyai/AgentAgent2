# AgentAgent2 harness — zero required third-party dependencies, so this image needs
# nothing beyond a slim Python base and the package itself.
FROM python:3.12-slim

WORKDIR /app

# Copy only what's needed to install before the rest of the source, for better layer caching.
COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

# Tool calls (run_shell, filesystem writes) are sandboxed to this directory by the CLI/server's
# --workspace flag. Runs as a non-root user; the workspace is owned by it, not root.
RUN useradd --create-home --uid 1000 agent \
    && mkdir -p /workspace \
    && chown agent:agent /workspace
USER agent
WORKDIR /workspace

EXPOSE 8420

ENTRYPOINT ["agentagent2"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8420", "--workspace", "/workspace"]
