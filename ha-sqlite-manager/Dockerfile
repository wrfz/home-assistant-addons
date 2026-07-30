FROM python:3.12-alpine

RUN apk add --no-cache sqlite

COPY requirements.txt /opt/
RUN pip install --no-cache-dir -r /opt/requirements.txt

COPY app.py /opt/
COPY templates /opt/templates/

CMD ["python3", "/opt/app.py"]
