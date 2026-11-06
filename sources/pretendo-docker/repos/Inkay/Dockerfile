FROM ghcr.io/wiiu-env/devkitppc:20240505@sha256:54656be0864c518a7da9405acf4e7723e8ca38078feaf12362bed6ae34d0ea9e

COPY --from=ghcr.io/wiiu-env/libnotifications:20240426  /artifacts $DEVKITPRO
COPY --from=ghcr.io/wiiu-env/libfunctionpatcher:20230621 /artifacts $DEVKITPRO
COPY --from=ghcr.io/wiiu-env/libkernel:20230621 /artifacts $DEVKITPRO
COPY --from=ghcr.io/wiiu-env/libmocha:20231127 /artifacts $DEVKITPRO
COPY --from=ghcr.io/wiiu-env/wiiupluginsystem:20240505 /artifacts $DEVKITPRO

WORKDIR /app
CMD make -f Makefile -j$(nproc)