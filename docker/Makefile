
# set for docker or podman
CONTAINER_ENGINE ?= podman

.PHONY: container-run
container-run:
	$(CONTAINER_ENGINE)-compose down  &&\
	       	$(CONTAINER_ENGINE)-compose up -d --build
