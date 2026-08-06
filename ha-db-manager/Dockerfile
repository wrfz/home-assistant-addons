FROM python:3.14-alpine

RUN apk add --no-cache sqlite

COPY requirements.txt /opt/
RUN pip install --no-cache-dir -r /opt/requirements.txt

COPY config.yaml /opt/
COPY app.py /opt/
COPY db.py /opt/
COPY run.sh /opt/
COPY static /opt/static/

CMD ["sh", "/opt/run.sh"]
