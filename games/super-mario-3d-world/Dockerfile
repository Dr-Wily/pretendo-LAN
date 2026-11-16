# D'après le Dockerfile du dépôt d'origine, avec les images de base figées par leur empreinte.
# Go 1.23.9 : au moins la version demandée par go.mod (toolchain go1.23.4), sans téléchargement d'une autre.
FROM golang:1.23-alpine3.20@sha256:96917b18cf0bf6dc54f726696eb526fe6e6a1ab45e43d4a292aae11f3d503ffe AS build
ENV GOTOOLCHAIN=local CGO_ENABLED=0
WORKDIR /home/go/app
COPY src/go.mod src/go.sum ./
RUN go mod download
COPY src/ .
RUN go build -ldflags "-X 'main.serverBuildString=pretendo-lan.super-mario-3d-world'" -o build/server

FROM alpine:3.20@sha256:d9e853e87e55526f6b2917df91a2115c36dd7c696a35be12163d44e6e2a4b6bc
WORKDIR /home/go/app
RUN addgroup go && adduser -D -G go go && mkdir -p log && chown go:go log
USER go
COPY --from=build /home/go/app/build/server ./server
CMD ["./server"]
