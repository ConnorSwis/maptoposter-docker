# --- STAGE 1 : BUILDER (Compilation) ---
FROM python:3.14-slim AS builder

# 1. Build tools
RUN apt-get update && apt-get install -y \
    build-essential \
    libspatialindex-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Isolated virtualenv
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 3. Install deps (copy requirements first for better caching)
COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install --only-binary=:all: --no-cache-dir -r requirements.txt

# 4. Copy the rest of the project
COPY . .


# --- STAGE 2 : RUNTIME (Production) ---
FROM python:3.14-slim

# 1. Runtime system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libspatialindex8 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Copy venv and app from builder
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app /app

# 3. Runtime config
ENV PATH="/opt/venv/bin:$PATH"
ENV MPLBACKEND=Agg

EXPOSE 5025

CMD ["python", "run.py"]