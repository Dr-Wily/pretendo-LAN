# D'après le Dockerfile du dépôt d'origine, avec les images de base figées par leur empreinte.
# Go 1.25.11 : au moins la version demandée par go.mod (go 1.25.0), sans téléchargement d'une autre.
FROM golang:1.25-alpine3.22@sha256:65b4400aee0927412e9ed791a11893273a49d55df24841f7599660fb80dae464 AS build
ENV GOTOOLCHAIN=local CGO_ENABLED=0
WORKDIR /home/go/app
COPY src/go.mod src/go.sum ./
RUN go mod download
COPY src/ .
RUN go build -o build/server .

FROM alpine:3.22@sha256:49340b346798875b5592e5d420241f2f9cfba5f47e62ebb1446a1b34734e898f
WORKDIR /home/go/app
RUN addgroup go && adduser -D -G go go && mkdir -p log && chown -R go:go /home/go/app
USER go
COPY --from=build /home/go/app/build/server ./server
CMD ["./server"]
