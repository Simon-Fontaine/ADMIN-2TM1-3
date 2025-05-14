FROM python:3.12.3-bookworm

RUN pip install -U pip setuptools wheel

WORKDIR /project

COPY requirements.txt ./
RUN pip install -r requirements.txt --no-cache-dir

COPY . .

CMD [ "python", "main.py" ]