FROM python:3.14
WORKDIR /jeoparty

# Expose the provided port for Flask
EXPOSE $PORT

# Copy pyproject.toml
COPY pyproject.toml pdm.lock ./

# Set environment variables
ENV PDM_HOME=/bin

# Download PDM and install requirements
RUN curl -sSL https://pdm-project.org/install.sh | bash && pdm install

# Copy code and resources
COPY src ./src
COPY resources ./resources

# Run the server
WORKDIR /jeoparty/src
CMD ["pdm", "run", "main.py", "-p", "${PORT}"]