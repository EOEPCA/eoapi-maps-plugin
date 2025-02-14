#!/bin/sh

set -e -x

cp /etc/config.yaml /config/config.yaml
pygeoapi openapi generate /etc/config.yaml --output-file=/config/openapi.yaml
