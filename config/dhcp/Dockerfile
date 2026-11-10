# DHCP de Pretendo LAN : dnsmasq seul (son DNS est désactivé : coredns-public sert le port 53).
# Image de base figée par son empreinte (versions.env, BASE_IMAGES).
FROM alpine:3.20@sha256:d9e853e87e55526f6b2917df91a2115c36dd7c696a35be12163d44e6e2a4b6bc
RUN apk add --no-cache dnsmasq && dnsmasq --version | head -1
ENTRYPOINT ["dnsmasq", "-k", "--conf-file=/etc/dnsmasq-lan/dnsmasq.conf"]
