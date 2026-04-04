pushd $(dirname $0)

# Clean up old image
podman stop -i jeoparty_test

# Build latest image and run container
podman build . -t jeoparty_test:latest --target test --env DEPGROUP=dev
podman image prune -f

bind_mounts=( "./tests/screenshots" "./tests/videos" )
for path in "${bind_mounts[@]}"
do
    if [[ ! -d "$path" ]]; then
        mkdir "$path"
    fi
done

podman run \
    --name jeoparty_test \
    -i \
    --rm \
    -v ./src/jeoparty/app/static/data/packs:/jeoparty/src/jeoparty/app/static/data/packs \
    -v ./tests/screenshots:/jeoparty/tests/screenshots \
    -v ./tests/videos:/jeoparty/tests/videos \
    jeoparty_test:latest

popd