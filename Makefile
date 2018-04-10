ifeq ($(TARGET), rhel)
    DOCKERFILE := Dockerfile.rhel

    ifndef DOCKER_REGISTRY
        $(error DOCKER_REGISTRY is not set)
    endif

    REGISTRY := $(DOCKER_REGISTRY)
else
    DOCKERFILE := Dockerfile
    REGISTRY?=registry.devshift.net
endif
REPOSITORY?=bayesian/cucos-worker
DEFAULT_TAG=latest

.PHONY: all docker-build fast-docker-build test get-image-name get-image-repository

all: fast-docker-build

docker-build:
	cp Dockerfile.rhel.template Dockerfile.rhel
	sed -i "s/__REGISTRY__/$(REGISTRY)/g" Dockerfile.rhel
	docker build --no-cache -t $(REGISTRY)/$(REPOSITORY):$(DEFAULT_TAG) -f $(DOCKERFILE) .
	docker tag $(REGISTRY)/$(REPOSITORY):$(DEFAULT_TAG) $(REPOSITORY):$(DEFAULT_TAG)

docker-build-tests: docker-build
	docker build --no-cache -t worker-tests -f Dockerfile.tests .

fast-docker-build:
	cp Dockerfile.rhel.template Dockerfile.rhel
	sed -i "s/__REGISTRY__/$(REGISTRY)/g" Dockerfile.rhel
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
