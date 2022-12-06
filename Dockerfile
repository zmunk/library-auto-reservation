FROM selenium/standalone-chrome
# Python 3.8.10

USER root

ENV AWS_DEFAULT_REGION=us-east-1
ENV VIRTUAL_ENV=/opt/env
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

COPY . .

RUN apt-get update && apt-get install -y python3-distutils python3.8-venv
RUN python3 -m venv $VIRTUAL_ENV
RUN pip3 install -r requirements.txt

CMD ["python3", "app.py"]
