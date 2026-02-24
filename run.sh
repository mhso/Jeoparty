pushd $(dirname $0)

port=5006

# Clean up old image
podman stop -i jeoparty
podman rm -i jeoparty

# Build latest image and run container
podman build . -t jeoparty:latest --env PORT=$port
podman run \
    --name jeoparty \
    -i \
    -p \
    $port:$port \
    -v ./log:/jeoparty/log \
    -v ./resources/database:/jeoparty/resources/database \
    -v ./src/jeoparty/app/static/data/packs:/jeoparty/src/jeoparty/app/static/data/packs \
    jeoparty:latest

popd