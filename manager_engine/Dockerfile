# Build argument for environment
ARG ENV=production

# Use environment-specific base image
FROM python:3.9-slim

RUN apt-get update && apt-get install -y \
    iputils-ping \
    ldap-utils \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Set environment variable for build
ENV ENV=${ENV}

# Copy the requirements file into the container at /app
COPY requirements.txt ./

# Install any needed packages specified in requirements.txt
RUN if [ "$ENV" = "development" ]; then \
    pip install --no-cache-dir -r requirements.txt; \
    else \
    pip install --trusted-host pstore.artifactory.cec.lab.emc.com --no-cache-dir -r requirements.txt; \
    fi

# Install gunicorn for production WSGI server
RUN pip install --no-cache-dir gunicorn==21.2.0

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser -u 1000 appuser

# Copy the current directory contents into the container at /app
COPY --chown=appuser:appuser . /app

# Make port 5000 available to the world outside this container
EXPOSE 5002
ENV FLASK_APP=app.py
ENV FLASK_RUN_PORT=5002

# Switch to non-root user
USER appuser

# Run Flask with gunicorn production WSGI server
CMD ["gunicorn", "--bind", "0.0.0.0:5002", "--workers", "4", "--timeout", "120", "app:app"]
