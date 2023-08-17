FROM python:3.11-slim

ENV BOT_NAME=$BOT_NAME

WORKDIR /usr/src/app/${BOT_NAME}

COPY requirements.txt /usr/src/app/${BOT_NAME}
RUN pip install -r /usr/src/app/${BOT_NAME}/requirements.txt
RUN python -m spacy download ru_core_news_sm
COPY . /usr/src/app/${BOT_NAME}
