# Use official Python image
FROM python:3.13-slim

# Install curl
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Download the latest uv installer
ADD https://astral.sh/uv/install.sh /uv-installer.sh

# Run the uv installer then remove it
RUN sh /uv-installer.sh && rm /uv-installer.sh

# Ensure the installed binary is on the `PATH`
ENV PATH="/root/.local/bin/:$PATH"

COPY . /app
WORKDIR /app

RUN uv export --no-dev  > requirements.txt && \
    uv pip install --system -r requirements.txt

# Expose port
EXPOSE 8000

# Start server
CMD ["python", "main.py"]
