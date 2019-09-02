REGISTRY?=quay.io
DEFAULT_TAG=latest
TESTS_IMAGE=worker-tests

ifeq ($(TARGET), rhel)
    DOCKERFILE := Dockerfile.rhel
	REPOSITORY ?= openshiftio/rhel-bayesian-cucos-worker
else
    DOCKERFILE := Dockerfile
	REPOSITORY ?= openshiftio/bayesian-cucos-worker
endif

.PHONY: all docker-build fast-docker-build test get-image-name get-image-repository

all: fast-docker-build

docker-build:
	docker build --no-cache -t $(REGISTRY)/$(REPOSITORY):$(DEFAULT_TAG) -f $(DOCKERFILE) .
	docker tag $(REGISTRY)/$(REPOSITORY):$(DEFAULT_TAG) $(REPOSITORY):$(DEFAULT_TAG)

docker-build-tests: docker-build
	docker build --no-cache -t $(TESTS_IMAGE) -f Dockerfile.tests .

fast-docker-build:
	docker build -t $(REGISTRY)/$(REPOSITORY):$(DEFAULT_TAG) -f $(DOCKERFILE) .
	docker tag $(REGISTRY)/$(REPOSITORY):$(DEFAULT_TAG) $(TESTS_IMAGE):$(DEFAULT_TAG)

fast-docker-build-tests: fast-docker-build
	docker build -t $(TESTS_IMAGE) -f Dockerfile.tests .

test: fast-docker-build-tests
	./qa/runtest.sh

get-image-name:
	@echo $(REGISTRY)/$(REPOSITORY):$(DEFAULT_TAG)

get-image-name-base:
	@echo $(REGISTRY)/$(REPOSITORY)

get-image-repository:
	@echo $(REPOSITORY)
