# Stage 1: Build Haskell Binary
FROM haskell:9.6.6 as builder

WORKDIR /build
# Copy only the haskell part first for better caching
COPY cvi-backend /build/cvi-backend
WORKDIR /build/cvi-backend

# Build the binary
# --system-ghc ensures it uses the one in the image (9.6.6)
# matches lts-22.43 exactly
RUN stack build --system-ghc --copy-bins --local-bin-path /usr/local/bin

# Stage 2: Final Runtime Image
FROM python:3.11-slim

# Install system dependencies for the Haskell binary
RUN apt-get update && apt-get install -y \
    libgmp10 \
    libffi8 \
    libnuma1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the compiled Haskell binary from builder
COPY --from=builder /usr/local/bin/cvi-backend /usr/local/bin/cvi-backend

# Copy python project parts
COPY requirements.txt /app/requirements.txt
COPY python_runner /app/python_runner
COPY webapp /app/webapp

# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Render sets PORT dynamically; default to 10000 if not set
ENV PORT=10000
EXPOSE $PORT

WORKDIR /app/webapp
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:$PORT --timeout 120 --workers 2 app:app"]
