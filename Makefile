IMAGE_ALPINE ?= spectranext/sdk-alpine
IMAGE_UBUNTU ?= spectranext/sdk-ubuntu
TAG ?= latest
CONTEXT ?= .
DOCKERFILE_ALPINE ?= Dockerfile.alpine
DOCKERFILE_UBUNTU ?= Dockerfile.ubuntu
PLATFORMS ?= linux/amd64,linux/arm64
# Multi-platform builds need the docker-container driver (not default "docker" on Docker Desktop).
BUILDX_BUILDER ?= spectranext-multiarch
BUILDX := docker buildx build --builder $(BUILDX_BUILDER)

.PHONY: help setup-buildx \
	build build-alpine build-ubuntu \
	build-alpine-amd64 build-alpine-arm64 build-ubuntu-amd64 build-ubuntu-arm64 \
	build-all build-all-amd64 build-all-arm64 build-all-multi \
	push push-alpine push-ubuntu push-all \
	push-alpine-amd64 push-alpine-arm64 push-ubuntu-amd64 push-ubuntu-arm64

help:
	@printf '%s\n' \
		'Targets:' \
		'  build              Build alpine + ubuntu for the current Docker platform' \
		'  build-alpine       Build alpine image locally' \
		'  build-ubuntu       Build ubuntu image locally' \
		'  build-alpine-amd64 Build and load alpine linux/amd64' \
		'  build-alpine-arm64 Build and load alpine linux/arm64' \
		'  build-ubuntu-amd64 Build and load ubuntu linux/amd64' \
		'  build-ubuntu-arm64 Build and load ubuntu linux/arm64' \
		'  build-all          Alias for build' \
		'  build-all-amd64    Build alpine + ubuntu linux/amd64' \
		'  build-all-arm64    Build alpine + ubuntu linux/arm64' \
		'  build-all-multi    Build both images for amd64+arm64 (no push, no --load)' \
		'  setup-buildx       Create/bootstrap buildx builder for multi-platform builds' \
		'  push               Push multi-arch manifests for alpine + ubuntu' \
		'  push-alpine        Push alpine multi-arch manifest' \
		'  push-ubuntu        Push ubuntu multi-arch manifest' \
		'  push-all           Alias for push' \
		'  push-alpine-amd64  Push alpine linux/amd64 only' \
		'  push-alpine-arm64  Push alpine linux/arm64 only' \
		'  push-ubuntu-amd64  Push ubuntu linux/amd64 only' \
		'  push-ubuntu-arm64  Push ubuntu linux/arm64 only' \
		'' \
		'Variables:' \
		'  IMAGE_ALPINE=spectranext/sdk-alpine IMAGE_UBUNTU=spectranext/sdk-ubuntu' \
		'  TAG=latest PLATFORMS=linux/amd64,linux/arm64 BUILDX_BUILDER=spectranext-multiarch'

setup-buildx:
	@if ! docker buildx inspect $(BUILDX_BUILDER) >/dev/null 2>&1; then \
		echo "Creating buildx builder '$(BUILDX_BUILDER)' (docker-container driver)..."; \
		docker buildx create --name $(BUILDX_BUILDER) --driver docker-container; \
	fi
	@docker buildx inspect --bootstrap $(BUILDX_BUILDER) >/dev/null

build: build-alpine build-ubuntu
build-all: build

build-alpine:
	docker build -f $(DOCKERFILE_ALPINE) -t $(IMAGE_ALPINE):$(TAG) $(CONTEXT)

build-ubuntu:
	docker build -f $(DOCKERFILE_UBUNTU) -t $(IMAGE_UBUNTU):$(TAG) $(CONTEXT)

build-alpine-amd64:
	docker buildx build --platform linux/amd64 -f $(DOCKERFILE_ALPINE) -t $(IMAGE_ALPINE):$(TAG)-amd64 --load $(CONTEXT)

build-alpine-arm64:
	docker buildx build --platform linux/arm64 -f $(DOCKERFILE_ALPINE) -t $(IMAGE_ALPINE):$(TAG)-arm64 --load $(CONTEXT)

build-ubuntu-amd64:
	docker buildx build --platform linux/amd64 -f $(DOCKERFILE_UBUNTU) -t $(IMAGE_UBUNTU):$(TAG)-amd64 --load $(CONTEXT)

build-ubuntu-arm64:
	docker buildx build --platform linux/arm64 -f $(DOCKERFILE_UBUNTU) -t $(IMAGE_UBUNTU):$(TAG)-arm64 --load $(CONTEXT)

build-all-amd64: build-alpine-amd64 build-ubuntu-amd64
build-all-arm64: build-alpine-arm64 build-ubuntu-arm64

build-all-multi: setup-buildx
	$(BUILDX) --platform $(PLATFORMS) -f $(DOCKERFILE_ALPINE) -t $(IMAGE_ALPINE):$(TAG) $(CONTEXT)
	$(BUILDX) --platform $(PLATFORMS) -f $(DOCKERFILE_UBUNTU) -t $(IMAGE_UBUNTU):$(TAG) $(CONTEXT)

push: push-alpine push-ubuntu
push-all: push

push-alpine: setup-buildx
	$(BUILDX) --platform $(PLATFORMS) -f $(DOCKERFILE_ALPINE) -t $(IMAGE_ALPINE):$(TAG) --push $(CONTEXT)

push-ubuntu: setup-buildx
	$(BUILDX) --platform $(PLATFORMS) -f $(DOCKERFILE_UBUNTU) -t $(IMAGE_UBUNTU):$(TAG) --push $(CONTEXT)

push-alpine-amd64:
	docker buildx build --platform linux/amd64 -f $(DOCKERFILE_ALPINE) -t $(IMAGE_ALPINE):$(TAG)-amd64 --push $(CONTEXT)

push-alpine-arm64:
	docker buildx build --platform linux/arm64 -f $(DOCKERFILE_ALPINE) -t $(IMAGE_ALPINE):$(TAG)-arm64 --push $(CONTEXT)

push-ubuntu-amd64:
	docker buildx build --platform linux/amd64 -f $(DOCKERFILE_UBUNTU) -t $(IMAGE_UBUNTU):$(TAG)-amd64 --push $(CONTEXT)

push-ubuntu-arm64:
	docker buildx build --platform linux/arm64 -f $(DOCKERFILE_UBUNTU) -t $(IMAGE_UBUNTU):$(TAG)-arm64 --push $(CONTEXT)
