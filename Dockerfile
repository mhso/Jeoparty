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

# Set environment variables
ENV UV_INSTALL_DIR=/bin

# Copy pyproject.toml
COPY pyproject.toml uv.lock ./

# Download uv and install requirements
RUN curl -LsSf https://astral.sh/uv/install.sh | bash && uv sync --no-dev

# Move back to test at some point...
RUN uv run playwright install chromium

# Copy code and resources
COPY src ./src
COPY resources/locales ./resources/locales

# -=-=-=- Test Stage -=-=-=-
FROM base AS test

COPY tests ./tests

# Run the tests
CMD ["uv", "run", "pytest", "tests/test_full_game.py", "--tb", "short", "-s"]

# -=-=-=- Production Stage -=-=-=-
FROM base AS prod

# Run the server
WORKDIR /jeoparty/src
CMD uv run main.py -p ${PORT} -e production --spa
