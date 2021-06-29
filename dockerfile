# set base image (host OS)
FROM python:3.8-slim
    
    # set the working directory in the container
    WORKDIR /code

    # copy the dependencies file to the working directory
    COPY requirements.txt .

    # install dependencies
    RUN apt-get update \
        && apt-get install -y --no-install-recommends gcc libc-dev \
        && rm -rf /var/lib/apt/lists/* \
        && pip install -r requirements.txt \
        && apt-get purge -y --auto-remove gcc libc-dev
        
    # copy the content of the local src directory to the working directory
    ADD . .

    # command to run on container start
    CMD [ "python", "src/server_app.py" ]