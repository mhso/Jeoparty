# -=-=-=- Base Stage -=-=-=-
FROM python:3.14-trixie AS base
WORKDIR /jeoparty

# Install root system dependencies
RUN apt update \
    && apt install -y libnspr4 \
    && apt install -y libnss3 \
    && apt install -y libatk1.0-0t64 \
    && apt install -y libatk-bridge2.0-0t64 \
    && apt install -y libxcomposite1 \
    && apt install -y libxdamage1 \
    && apt install -y libxfixes3 \
    && apt install -y libxrandr2 \
    && apt install -y libgbm1 \
    && apt install -y libxkbcommon0 \
    && apt install -y libasound2t64

# Copy pyproject.toml
COPY pyproject.toml pdm.lock ./

# Set environment variables
ENV PDM_HOME=/bin

# Download PDM and install requirements
RUN curl -sSL https://pdm-project.org/install.sh | bash && pdm install --$DEPGROUP

# Copy code and resources
COPY src ./src
COPY resources/schema.sql ./resources/schema.sql
COPY resources/locales ./resources/locales

# -=-=-=- Test Stage -=-=-=-
FROM base AS test

RUN pdm run playwright install chromium

COPY tests ./tests
COPY resources/database/database.db ./resources/database/database.db

# Run the tests
CMD ["pdm", "run", "pytest"]

# -=-=-=- Production Stage -=-=-=-
FROM base AS prod

# Expose the provided port for Flask
EXPOSE $PORT

# Run the server
WORKDIR /jeoparty/src
CMD ["pdm", "run", "main.py", "-p", "${PORT}"]
