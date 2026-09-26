# Isolated inference gateway for the Jev experiment.
#
#   docker build -t jev-gateway:1 gateway
#
# Holds the provider credential. Contains no agent code, no Omega, no Python,
# no StickerBook authority. Runs on the egress network AND the internal
# network; the agent runs only on the internal one, so the agent has no route
# to the Internet at all.
#
# The stock nginx image substitutes ${OPENROUTER_API_KEY} into
# /etc/nginx/conf.d/default.conf at start via its envsubst entrypoint, so the
# key exists only in this container's memory and generated config.

FROM nginx:1.27-alpine

# Replaces the stock default.conf, so no other route is served.
COPY default.conf.template /etc/nginx/templates/default.conf.template

# Substitute only this one variable; leave nginx's own $vars alone.
ENV NGINX_ENVSUBST_FILTER="OPENROUTER_API_KEY"

EXPOSE 8080
