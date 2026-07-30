ARG BUILD_FROM
FROM ${BUILD_FROM}

RUN apk add --no-cache python3 py3-pip

COPY requirements.txt /opt/
RUN pip3 install --no-cache-dir --break-system-packages -r /opt/requirements.txt

COPY run.sh /
RUN chmod a+x /run.sh

CMD ["/run.sh"]
