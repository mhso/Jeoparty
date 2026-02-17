port=5006

# Build latest image and run container
podman build . -t jeoparty:latest --env PORT=$port
podman run --name jeoparty -p $port:$port -d --replace jeoparty:latest

# Clean up old images
podman image prune -f > /dev/null