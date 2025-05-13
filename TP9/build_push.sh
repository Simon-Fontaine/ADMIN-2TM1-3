#!/bin/bash

set -e

username="simonschool"
version="1.0"

docker build -t $username/woody_api:$version services/api
docker build -t $username/woody_rp:$version services/reverse-proxy
docker build -t $username/woody_database:$version services/database
docker build -t $username/woody_front:$version services/front

docker tag $username/woody_api:$version $username/woody_api:latest
docker tag $username/woody_rp:$version $username/woody_rp:latest
docker tag $username/woody_database:$version $username/woody_database:latest
docker tag $username/woody_front:$version $username/woody_front:latest

docker login

docker push $username/woody_api:$version
docker push $username/woody_api:latest
docker push $username/woody_rp:$version
docker push $username/woody_rp:latest
docker push $username/woody_database:$version
docker push $username/woody_database:latest
docker push $username/woody_front:$version
docker push $username/woody_front:latest