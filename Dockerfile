FROM python:3.9.1-alpine

WORKDIR /app

COPY requirements.txt ./
RUN pip install -Ur requirements.txt

# Make Docker /config volume for optional config file
VOLUME /config

# Copy example config file from build machine to Docker /config folder
COPY config.json* /config/

# Copy source code from build machine to WORKDIR (/app) folder
COPY . .

# Delete unnecessary files in WORKDIR (/app) folder (not caught by .dockerignore)
RUN echo "**** removing unneeded files ****"
RUN rm -rf requirements.txt

CMD [ "python", "regrabbar.py" ]