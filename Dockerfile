FROM python:3.12.5-alpine AS build

ARG VERSION
RUN test -z "${VERSION}" && echo "No 'VERSION' argument provided, exiting" \
	&& exit 1 || true

COPY . /usr/src/
WORKDIR /usr/src/

# Rust and Cargo are required to build `pyndatic-core` on ARM platforms
RUN apk add -U cargo git rust \
	&& pip install build \
	&& apk cache clean
# Install dependencies in a separate layer to cache them
RUN pip install --root target/ -r requirements.txt
# Build the package

RUN SETUPTOOLS_SCM_PRETEND_VERSION_FOR_ENERGOMERA_HASS_MQTT=${VERSION} python -m build \
	&& pip install --root target/ dist/*-${VERSION}*.whl

FROM python:3.12.5-alpine
COPY --from=build \
	/usr/src/target/root/.local/lib/ \
	/usr/src/target/usr/local/lib/ \
	/usr/local/lib/
COPY --from=build \
	/usr/src/target/usr/local/bin/ \
	/usr/local/bin/

ENTRYPOINT ["energomera-hass-mqtt"]
