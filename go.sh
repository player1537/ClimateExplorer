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

Server_bind=127.0.0.1
Server_host=127.0.0.1
Server_port=5000

go-Server() {
    FLASK_APP='vaas/app:app' \
    FLASK_RUN_HOST=${Server_bind:?} \
    FLASK_RUN_PORT=${Server_port:?} \
    pexec flask run \
        ##
}

Integrate_url=http://${Server_host:?}:${Server_port:?}/flow/integrate
Integrate_t0=0.0
Integrate_y0=13.37,13.37,13.37
Integrate_tf=100000

go-Integrate() {
    exec < <(pexec curl \
        --silent \
        --get \
        "${Integrate_url:?}" \
        --data-urlencode t0="${Integrate_t0:?}" \
        --data-urlencode y0="${Integrate_y0:?}" \
        --data-urlencode tf="${Integrate_tf:?}" \
        ##
    )

    pexec python3 -m json.tool \
        ##
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

