FROM geopython/pygeoapi

RUN mkdir /emp
WORKDIR /emp

COPY requirements.txt .
RUN python3 -m pip install -r requirements.txt

COPY . .

RUN python3 setup.py install
