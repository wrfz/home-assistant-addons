ARG BUILD_FROM
FROM ${BUILD_FROM}

RUN apk add --no-cache python3 py3-pip py3-aiohttp

COPY requirements.txt /opt/
RUN pip3 install --no-cache-dir --break-system-packages -r /opt/requirements.txt

COPY app.py /opt/
COPY templates /opt/templates/
COPY rootfs /

ENTRYPOINT ["/init"]
