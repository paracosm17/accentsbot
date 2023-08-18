FROM python:3.11-slim

ENV BOT_NAME=$BOT_NAME

WORKDIR /usr/src/app/${BOT_NAME}

COPY requirements.txt /usr/src/app/${BOT_NAME}
RUN pip install -U pip setuptools wheel && pip install -U spacy && pip install https://github.com/explosion/spacy-models/releases/download/ru_core_news_sm-3.6.0/ru_core_news_sm-3.6.0.tar.gz
RUN pip install -r /usr/src/app/${BOT_NAME}/requirements.txt
COPY . /usr/src/app/${BOT_NAME}
