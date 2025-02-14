FROM geopython/pygeoapi:0.19.0

LABEL org.opencontainers.image.source https://github.com/EOEPCA/eoapi-maps-plugin

RUN mkdir /emp
WORKDIR /emp

ENV PYGEOAPI_CONFIG \
    PYGEOAPI_OPENAPI

COPY requirements.txt .
RUN python3 -m pip install -r requirements.txt

COPY . .

RUN python3 setup.py install

EXPOSE 5000

ENTRYPOINT [ "" ]
CMD ["gunicorn", "pygeoapi.flask_app:APP", "--workers=4", "--bind=0.0.0.0:5000", "--reload", "--reload-extra-file=/config/config.yaml"]
