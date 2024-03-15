FROM python:3.13.0a4-alpine as build
RUN apk add -U git
RUN pip install build
ADD . src/
WORKDIR src
RUN python -m build
RUN pip install --root target/ dist/*-`cat version.txt`*.whl

FROM python:3.13.0a4-alpine
COPY --from=build \
	src/target/root/.local/lib/ /usr/local/lib/
COPY --from=build \
	src/target/root/.local/bin/ \
	/usr/local/bin/

ENTRYPOINT ["energomera-hass-mqtt"]
