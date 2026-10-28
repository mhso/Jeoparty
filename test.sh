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

# Build frontend
#podman build ../jeoparty_web -t jeoparty_web:latest --output type=local,dest=../jeoparty_web/dist

podman run \
    --name jeoparty_test \
    -i \
    --rm \
    --network=host \
    -e USE_DOCKER=1 \
    -v ./src/jeoparty/app/static/data/packs:/jeoparty/src/jeoparty/app/static/data/packs \
    -v ../jeoparty_web/dist:/jeoparty/dist \
    -v ./tests/screenshots:/jeoparty/tests/screenshots \
    -v ./tests/videos:/jeoparty/tests/videos \
    -v /mnt/d/mhooge/jeoparty_web/src/shared/locales:/jeoparty_web/src/shared/locales \
    jeoparty_test:latest

podman stop -i postgres_test

popd