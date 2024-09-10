FROM python:3.12.5-alpine AS build
COPY . /usr/src/
WORKDIR /usr/src/
# Rust and Cargo are required to build `pyndatic-core` on ARM platforms
RUN apk add -U cargo git rust \
	&& pip install build \
	&& apk cache clean
# Install dependencies in a separate layer to cache them
RUN --mount=type=cache,target=/root/.cache/pip pip install --root target/ -r requirements.txt
# Build the package
RUN --mount=type=cache,target=/root/.cache/pip python -m build \
	&& pip install --root target/ dist/*-`cat version.txt`*.whl

FROM python:3.12.5-alpine
COPY --from=build \
	/usr/src/target/root/.local/lib/ /usr/local/lib/
COPY --from=build \
	/usr/src/target/root/.local/bin/ \
	/usr/local/bin/

ENTRYPOINT ["energomera-hass-mqtt"]
