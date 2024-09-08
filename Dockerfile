FROM python:3.13.0rc1-alpine AS build
# Rust and Cargo are required to build `pyndatic-core` on ARM platforms
RUN apk add -U cargo git rust \
	&& pip install build \
	&& apk cache clean
ADD . /usr/src/
WORKDIR /usr/src/
RUN python -m build
RUN pip install --root target/ dist/*-`cat version.txt`*.whl

FROM python:3.13.0rc1-alpine
COPY --from=build \
	/usr/src/target/root/.local/lib/ /usr/local/lib/
COPY --from=build \
	/usr/src/target/root/.local/bin/ \
	/usr/local/bin/

ENTRYPOINT ["energomera-hass-mqtt"]
