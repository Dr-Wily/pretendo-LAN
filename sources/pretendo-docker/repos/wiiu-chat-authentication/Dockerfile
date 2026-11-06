# syntax=docker/dockerfile:1

ARG app_dir="/home/go/app"


# * Building the application
FROM golang:1.22-alpine3.20@sha256:ffd1cc7cf6bd432b951db453439c546f388d8e63100b86b585d2432cbbfa4cea AS build
ARG app_dir

WORKDIR ${app_dir}

RUN --mount=type=cache,target=/go/pkg/mod/ \
	--mount=type=bind,source=go.sum,target=go.sum \
	--mount=type=bind,source=go.mod,target=go.mod \
	go mod download -x

COPY . .
RUN --mount=type=cache,target=/go/pkg/mod/ \
	CGO_ENABLED=0 go build -v -o ${app_dir}/build/server


# * Running the final application
FROM alpine:3.20@sha256:d9e853e87e55526f6b2917df91a2115c36dd7c696a35be12163d44e6e2a4b6bc AS final
ARG app_dir
WORKDIR ${app_dir}

RUN addgroup go && adduser -D -G go go

RUN mkdir -p ${app_dir}/log && chown go:go ${app_dir}/log

USER go

COPY --from=build ${app_dir}/build/server ${app_dir}/server

CMD [ "./server" ]
