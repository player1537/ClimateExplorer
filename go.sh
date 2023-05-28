#!/usr/bin/env bash
die() { printf $'Error: %s\n' "$*" >&2; exit 1; }
root=$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)
self=${root:?}/${BASH_SOURCE[0]##*/}
project=${root##*/}
pexec() { >&2 printf exec; >&2 printf ' %q' "$@"; >&2 printf '\n'; exec "$@"; }
#---

go---virtualenv() {
    pexec "${self:?}" virtualenv \
    exec "${self:?}" "$@"
}

Server_app=vaas/app:app
Server_bind=127.0.0.1
Server_host=127.0.0.1
Server_port=5000

go-Server() {
    FLASK_APP=${Server_app:?} \
    FLASK_RUN_HOST=${Server_bind:?} \
    FLASK_RUN_PORT=${Server_port:?} \
    pexec flask run \
        ##
}

go-Request() {
    local url
    url=${1:?need url}

    exec < <(pexec python3 -m base64 \
        ##
    )

    exec < <(pexec curl \
        --silent \
        --get \
        "${url:?}" \
        --data-urlencode code@- \
        ##
    )

    pexec cat

    pexec python3 -m json.tool \
        ##
}

Integrate_url=http://${Server_host:?}:${Server_port:?}/code/execute
Integrate_t0=0.0
Integrate_y0=13.37,13.37,13.37
Integrate_tf=100000

go-Integrate() {
    pexec "${self:?}" Request \
        "${Integrate_url:?}" \
        <<EOF
local t0 = ${Integrate_t0:?}
local y0 = { ${Integrate_y0:?} }
local tf = ${Integrate_tf:?}

return vaas_climate_integrate{t0=t0, y0=y0, tf=tf}
EOF
}


#---

virtualenv_path=${root:?}/venv
virtualenv_python=python3
virtualenv_install=(
    lupa
    numpy
    scipy
    flask
)

go-virtualenv() {
    "${FUNCNAME[0]:?}-$@"
}

go-virtualenv-create() {
    pexec "${virtualenv_python:?}" -m venv \
        "${virtualenv_path:?}" \
        ##
}

go-virtualenv-install() {
    pexec "${virtualenv_path:?}/bin/python" -m pip \
        install \
        "${virtualenv_install[@]}" \
        ##
}

go-virtualenv-exec() {
    source "${virtualenv_path:?}/bin/activate" && \
    pexec "$@"
}


#---
test -f "${root:?}/env.sh" && source "${_:?}"
go-"$@"

