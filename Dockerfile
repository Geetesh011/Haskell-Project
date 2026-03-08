# Stage 1: Build the Haskell Environment & Python App
FROM haskell:9.6

# Install Python 3 and pip
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Create and activate a virtual environment
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Set up working directory
WORKDIR /app

# Copy the code
COPY . /app

# Install Haskell dependencies and build
WORKDIR /app/cvi-backend
RUN stack setup && stack build --copy-bins --local-bin-path /usr/local/bin

# Install Python dependencies
WORKDIR /app
RUN pip3 install -r requirements.txt

# Run the app via Gunicorn
WORKDIR /app/webapp
# Render sets the PORT environment variable dynamically
ENV PORT=5000
EXPOSE $PORT

CMD ["sh", "-c", "gunicorn -b 0.0.0.0:$PORT app:app"]
