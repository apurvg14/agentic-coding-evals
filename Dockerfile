# Runs the agentic-coding-evals dashboard (and CLI) in a container.
#
#   docker build -t agenteval .
#   docker run --rm -p 8765:8765 agenteval          # open http://localhost:8765
#
# The harness core is pure stdlib; we install anthropic/openai so that real
# model runs (--model claude-* / gpt-*) work when an API key is provided at
# runtime (never baked into the image):
#
#   docker run --rm -p 8765:8765 --env-file .env agenteval
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install optional real-model SDKs first so this layer caches across code edits.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Application code.
COPY agenteval ./agenteval
COPY tasks ./tasks

# Results are written here; mount a volume to persist/inspect them on the host.
RUN mkdir -p results
VOLUME ["/app/results"]

EXPOSE 8765

# Bind to all interfaces so the port is reachable from the host; never auto-open
# a browser inside a container.
CMD ["python", "-m", "agenteval", "dashboard", "--host", "0.0.0.0", "--port", "8765", "--no-open"]
