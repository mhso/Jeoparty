pushd $(dirname $0)

port=5006

# Clean up old image
podman stop -i jeoparty
podman rm -i jeoparty

# Build latest image and run container
podman build . -t jeoparty:latest --target prod --env PORT=$port --env DEPGROUP=prod
podman image prune -f

bind_mounts=( "./resources/database" "./log" "./src/jeoparty/app/static/data/packs" "./src/jeoparty/app/static/img/avatars"  )
for path in "${bind_mounts[@]}"
do
    if [[ ! -d "$path" ]]; then
        mkdir "$path"
    fi
done
podman run \
    --name jeoparty \
    -i \
    -p $port:$port \
    -v ./log:/jeoparty/log \
    -v ./resources/database:/jeoparty/resources/database \
    -v ./src/jeoparty/app/static/data/packs:/jeoparty/src/jeoparty/app/static/data/packs \
    -v ./src/jeoparty/app/static/img/avatars:/jeoparty/src/jeoparty/app/static/img/avatars \
    jeoparty:latest

popd