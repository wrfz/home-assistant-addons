ARG BUILD_FROM
FROM alpine:3.21

RUN apk add --no-cache python3 py3-pip

COPY requirements.txt /opt/
RUN pip3 install --no-cache-dir --break-system-packages -r /opt/requirements.txt

COPY app.py /opt/
COPY templates /opt/templates/

CMD ["python3", "/opt/app.py"]
