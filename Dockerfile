FROM python:3.12.5-alpine AS build

WORKDIR /usr/src/

# Rust and Cargo are required to build `pyndatic-core` on ARM platforms
RUN apk add -U cargo git rust \
	&& pip install build \
	&& apk cache clean
# Install dependencies in a separate layer to cache them
RUN --mount=type=bind,target=source/ pip install --root /tmp/target/ -r source/requirements.txt

# Build the package
ARG VERSION
RUN test -z "${VERSION}" && echo "No 'VERSION' argument provided, exiting" \
	&& exit 1 || true

RUN --mount=type=bind,target=source/,rw SETUPTOOLS_SCM_PRETEND_VERSION_FOR_ENERGOMERA_HASS_MQTT=${VERSION} python -m build --outdir /tmp/dist/ source/ \
	&& pip install --root /tmp/target/ /tmp/dist/*-${VERSION}*.whl

FROM python:3.12.5-alpine
COPY --from=build \
	/tmp/target/usr/local/lib/ \
	/usr/local/lib/
COPY --from=build \
	/tmp/target/usr/local/bin/ \
	/usr/local/bin/

ENTRYPOINT ["energomera-hass-mqtt"]
