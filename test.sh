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

POSTGRES_IMAGE="postgres:16.13-trixie"

podman stop -i postgres_test

podman run \
    --name postgres_test \
    -d \
    --rm \
    -p 127.0.0.1:5432:5432 \
    -e POSTGRES_PASSWORD=password \
    -e POSTGRES_USER=mikkel \
    $POSTGRES_IMAGE

podman run \
    --name jeoparty_test \
    -i \
    --rm \
    --network=host \
    -v ./src/jeoparty/app/static/data/packs:/jeoparty/src/jeoparty/app/static/data/packs \
    -v ./tests/screenshots:/jeoparty/tests/screenshots \
    -v ./tests/videos:/jeoparty/tests/videos \
    jeoparty_test:latest

podman stop -i postgres_test

popd