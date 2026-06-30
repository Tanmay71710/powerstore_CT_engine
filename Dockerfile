# Build argument for environment
ARG ENV=production

# Environment-specific base images
ARG BASE_IMAGE_DEV=python:3.9-slim
ARG BASE_IMAGE_STAGING=durjpd.artifactory.cec.lab.emc.com/vxflexos-docker-local-mw/baseimages/python:3.9.5-slim
ARG BASE_IMAGE_PROD=durjpd.artifactory.cec.lab.emc.com/vxflexos-docker-local-mw/baseimages/python:3.9.5-slim

# Select base image dynamically based on environment
FROM ${BASE_IMAGE_DEV}
# To use environment-specific base images, build with:
# docker build --build-arg ENV=staging --build-arg BASE_IMAGE=${BASE_IMAGE_STAGING} -t app:staging .
# docker build --build-arg ENV=production --build-arg BASE_IMAGE=${BASE_IMAGE_PROD} -t app:prod .

# Set the working directory in the container
WORKDIR /usr/src/app

# Set environment variable for build
ENV ENV=${ENV}

# Copy the requirements file to the container
COPY requirements.txt .

# Install any required packages
RUN pip install --no-cache-dir -r requirements.txt

# Install vaultInteraction from appropriate PyPI based on environment
RUN if [ "$ENV" = "development" ]; then \
    pip install --no-cache-dir vaultInteraction; \
    else \
    pip install --trusted-host pstore.artifactory.cec.lab.emc.com --extra-index-url https://pstore.artifactory.cec.lab.emc.com/artifactory/api/pypi/cyclone-pypi/simple vaultInteraction; \
    fi

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser -u 1000 appuser

# Copy the entire project directory to the container
COPY --chown=appuser:appuser . .

# Expose the port for Flask (you can change this if needed)
EXPOSE 5000

# Set an environment variable to choose which app to run (default to app1)
ENV APP_NAME=app1
ENV APP_PORT=5000
ENV TEST_SET_NAME=""

# Switch to non-root user
USER appuser

# Command to run either app1 or app2
ENTRYPOINT ["/bin/bash", "-c", "if [ $APP_NAME = 'manager' ]; then python manager_engine/app.py; elif [ $APP_NAME = 'monitor' ]; then python monitor_engine/app.py else python execution_engine/app.py --port $APP_PORT --test_set_name $TEST_SET_NAME; fi"]
