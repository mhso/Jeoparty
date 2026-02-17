FROM python:3.14
WORKDIR /jeoparty

# Expose the provided port for Flask
EXPOSE $PORT

# Create user to run everything as
RUN useradd -m jeoparty && chown jeoparty /jeoparty -R
USER jeoparty

# Copy pyproject.toml
COPY --chown=jeoparty pyproject.toml pdm.lock ./

# Download and install PDM
ENV PDM_HOME=/home/jeoparty/.local/bin
ENV PATH=/home/jeoparty/.local/bin:$PATH

# Download PDM and install requirements
RUN curl -sSL https://pdm-project.org/install.sh | bash && pdm install

# Copy code and resources
COPY --chown=jeoparty src ./src
COPY --chown=jeoparty resources ./resources

# Run the server
WORKDIR /jeoparty/src
CMD ["pdm", "run", "main.py", "-p", "${PORT}"]