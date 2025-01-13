FROM python:3.14.0a3-alpine AS deps

# Rust and Cargo are required to build `pyndatic-core` on ARM platforms
RUN apk add -U cargo git rust \
	&& pip install build \
	&& apk cache clean

# Limit use of the build context to the requirements file only, to avoid cache
# invalidation when other files get changed
COPY requirements.txt .
# Install dependencies in a separate layer to cache them
RUN pip install --root /tmp/target/ -r requirements.txt

FROM python:3.14.0a3-alpine AS build

RUN pip install build

# Build the package
ARG VERSION
RUN test -z "${VERSION}" && echo "No 'VERSION' argument provided, exiting" \
	&& exit 1 || true

# Writeable mount is needed for src/*.egg-info the `setup` module wants to
# create. `pip install --no-deps` is to skip installing dependencies to the
# package thus requiring extra prerequisites and extending the build time -
# those already fulfilled by `deps` stage
RUN \
	--mount=type=bind,target=source/,rw \
	SETUPTOOLS_SCM_PRETEND_VERSION_FOR_ENERGOMERA_HASS_MQTT=${VERSION} \
	python -m build --outdir /tmp/dist/ source/ \
	&& pip install --no-deps --root /tmp/target/ /tmp/dist/*-${VERSION}*.whl

FROM python:3.14.0a3-alpine
# Ensure all the OS updates are applied to the resulting image
RUN apk -U upgrade \
	&& apk cache clean

COPY --from=deps \
	/tmp/target/usr/local/lib/ \
	/usr/local/lib/
COPY --from=build \
	/tmp/target/usr/local/lib/ \
	/usr/local/lib/
COPY --from=build \
	/tmp/target/usr/local/bin/ \
	/usr/local/bin/

ENTRYPOINT ["energomera-hass-mqtt"]
