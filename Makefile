REGISTRY?=registry.devshift.net
REPOSITORY?=bayesian/cucos-worker
DEFAULT_TAG=latest

ifeq ($(TARGET), rhel)
    DOCKERFILE := Dockerfile.rhel
else
    DOCKERFILE := Dockerfile
endif

.PHONY: all docker-build fast-docker-build test get-image-name get-image-repository

all: fast-docker-build

docker-build:
	docker build --no-cache -t $(REGISTRY)/$(REPOSITORY):$(DEFAULT_TAG) -f $(DOCKERFILE) .
	docker tag $(REGISTRY)/$(REPOSITORY):$(DEFAULT_TAG) $(REPOSITORY):$(DEFAULT_TAG)

docker-build-tests: docker-build
	docker build --no-cache -t worker-tests -f Dockerfile.tests .

fast-docker-build:
	docker build -t $(REGISTRY)/$(REPOSITORY):$(DEFAULT_TAG) -f $(DOCKERFILE) .
	docker tag $(REGISTRY)/$(REPOSITORY):$(DEFAULT_TAG) $(REPOSITORY):$(DEFAULT_TAG)

fast-docker-build-tests: fast-docker-build
	docker build -t worker-tests -f Dockerfile.tests .

test: fast-docker-build-tests
	./runtest.sh

get-image-name:
	@echo $(REGISTRY)/$(REPOSITORY):$(DEFAULT_TAG)

get-image-repository:
	@echo $(REPOSITORY)
