"""

"""

from __future__ import annotations
from base64 import urlsafe_b64decode as b64decode
from threading import Lock
from contextlib import contextmanager

from flask import Blueprint, g, request
from lupa import LuaRuntime, as_attrgetter

__all__ = [
    'app', 'execute',
]


#--- Interface

app = Blueprint(
    name='code',
    import_name=__name__,
)


@app.before_app_request
def register_code():
    def vaas_register(scope, name, callback):
        callbacks = g._vaas_code_callbacks
        callbacks[f'vaas_{scope}_{name}'] = callback
        
    g._vaas_code_callbacks = {}
    g.vaas_register = vaas_register


@app.route('/execute', methods=['GET'])
def app_execute():
    code = request.args.get('code')
    code = b64decode(code)
    code = code.decode('ascii')

    callbacks = g._vaas_code_callbacks

    return execute(code, callbacks)


#--- 

_g_lua: LuaRuntime = None
_g_lua_lock: Lock = Lock()


def __get_lua():
    lua = LuaRuntime(
        unpack_returned_tuples=True,
    )
    return lua


def _get_lua():
    global _g_lua

    if (lua := _g_lua) is not None:
        return lua

    _g_lua = __get_lua()

    assert (lua := _g_lua) is not None, \
        "Dev error: something went wrong initializing 'lua'"
    
    return lua


@contextmanager
def get_lua():
    with _g_lua_lock:
        yield _get_lua()


#--- Functionality

EXECUTE = r'''
function(untrusted_code, callbacks)
    local env = {};
    for key, value in python.iterex(callbacks.items()) do
        env[key] = value
    end
    env.print = print

    local untrusted_function, message = load(untrusted_code, nil, 't', env)
    if not untrusted_function then return nil, message end
    debug.sethook(function() error("timeout") end, "", 1e6)
    local success, ret = pcall(untrusted_function)
    debug.sethook()
    return success, ret
end
''' #/EXECUTE


def realize(x):
    try:
        keys = list(x.keys())
    except:
        return x
    else:
        if 1 in keys:
            return [realize(x[i]) for i in range(1, 1+len(x))]
        else:
            return { k: realize(v) for k, v in x.items() }


def execute(code, callbacks):
    with get_lua() as lua:
        execute = lua.eval(EXECUTE)

#         print(f'{code = }')
#         print(f'{callbacks = !r}')

        callbacks = as_attrgetter(callbacks)

        success, ret = execute(code, callbacks)
        if not success:
            if not isinstance(ret, Exception):
                ret = Exception(f'{ret!r}')
            raise ret

        ret = realize(ret)
        return ret
