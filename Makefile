IMAGE_ALPINE ?= spectranext/sdk-alpine
IMAGE_UBUNTU ?= spectranext/sdk-ubuntu
TAG ?= latest
SDK_VERSION ?= 0.1.0
CONTEXT ?= .
DOCKERFILE_ALPINE ?= Dockerfile.alpine
DOCKERFILE_UBUNTU ?= Dockerfile.ubuntu
PLATFORMS ?= linux/amd64,linux/arm64
PYTHON ?= python3
DIST_DIR ?= dist
HOMEBREW_ARCH ?= $(shell uname -m | sed 's/arm64/arm64/;s/x86_64/x86_64/')
HOMEBREW_PACKAGE := spectranext-sdk-$(SDK_VERSION)-macos-$(HOMEBREW_ARCH)
HOMEBREW_TARBALL := $(DIST_DIR)/$(HOMEBREW_PACKAGE).tar.gz
# Multi-platform builds need the docker-container driver (not default "docker" on Docker Desktop).
BUILDX_BUILDER ?= spectranext-multiarch
BUILDX := docker buildx build --builder $(BUILDX_BUILDER)

.PHONY: help setup-buildx \
	homebrew-tarball \
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
		'  homebrew-tarball   Build macOS Homebrew release tarball with vendored wheels' \
		'' \
		'Variables:' \
		'  IMAGE_ALPINE=spectranext/sdk-alpine IMAGE_UBUNTU=spectranext/sdk-ubuntu' \
		'  TAG=latest PLATFORMS=linux/amd64,linux/arm64 BUILDX_BUILDER=spectranext-multiarch' \
		'  SDK_VERSION=0.1.0 HOMEBREW_ARCH=arm64|x86_64 DIST_DIR=dist PYTHON=python3'

homebrew-tarball:
	rm -rf "$(DIST_DIR)/$(HOMEBREW_PACKAGE)"
	mkdir -p "$(DIST_DIR)/$(HOMEBREW_PACKAGE)/vendor/wheels"
	cp -R README.md requirements.txt source.sh source.ps1 install.sh install.ps1 install.bat "$(DIST_DIR)/$(HOMEBREW_PACKAGE)/"
	cp -R bin clibs cmake include "$(DIST_DIR)/$(HOMEBREW_PACKAGE)/"
	@if [ -d man ]; then cp -R man "$(DIST_DIR)/$(HOMEBREW_PACKAGE)/"; fi
	$(PYTHON) -m pip download --dest "$(DIST_DIR)/$(HOMEBREW_PACKAGE)/vendor/wheels" -r requirements.txt
	find "$(DIST_DIR)/$(HOMEBREW_PACKAGE)" -name '.DS_Store' -delete
	find "$(DIST_DIR)/$(HOMEBREW_PACKAGE)" -name '__pycache__' -type d -prune -exec rm -rf {} +
	tar -czf "$(HOMEBREW_TARBALL)" -C "$(DIST_DIR)" "$(HOMEBREW_PACKAGE)"
	shasum -a 256 "$(HOMEBREW_TARBALL)" > "$(HOMEBREW_TARBALL).sha256"
	@printf '%s\n' "Built $(HOMEBREW_TARBALL)"
	@cat "$(HOMEBREW_TARBALL).sha256"

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
