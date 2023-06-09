#!/usr/bin/env python3
"""

"""

from __future__ import annotations
from os import PathLike
from dataclasses import dataclass
from pathlib import Path
import struct
from contextlib import ExitStack, contextmanager
from typing import NewType, Union, BinaryIO
import random
import time
from threading import Lock
from base64 import urlsafe_b64decode as b64decode

from lupa import LuaRuntime
from flask import Blueprint, request, g
import numpy as np
from scipy.interpolate import (
    RegularGridInterpolator as Interpolator,
)
from scipy.integrate import (
    RK45 as Integrator,
)

__all__ = [
    'app',
    'Climate',
]


#--- Interface

_g_climate: Climate = None
_g_climate_lock: Lock = Lock()

app = Blueprint(
    name='flow',
    import_name=__name__,
)


@app.before_app_request
def register_climate():
    def integrate(args: Dict[str, Any]) -> List[Dict[str, Any]]:
        t0 = args['t0']
        y0 = args['y0']
        y0 = (y0[1], y0[2], y0[3])
        tf = args['tf']

        with get_climate() as climate:
            ret = []
            for t, y in climate.integrate(t0=t0, y0=y0, tf=tf):
                # print(f'{t=!r} {y=!r}')
                y = y.tolist()
                ret.append({ 't': t, 'y': y })

        return ret

    g.vaas_register('climate', 'integrate', integrate)


def __get_climate():
    root = Path(__file__).parent.parent / 'data'
    return Climate.from_files(
        ugrd=root / 'UGRD-144x73.dat',
        vgrd=root / 'VGRD-144x73.dat',
        vvel=root / 'VVEL-144x73.dat',
    )


def _get_climate():
    global _g_climate

    if (climate := _g_climate) is not None:
        return climate
    
    _g_climate = __get_climate()

    assert (climate := _g_climate) is not None, \
        "Dev error: something went wrong initializing 'climate'"
    
    return climate


@contextmanager
def get_climate():
    with _g_climate_lock:
        yield _get_climate()


@app.route('/integrate', methods=['GET'])
def integrate():
    climate = get_climate()
    lua = get_lua()

    run = request.args.get('run')
    run = b64decode(run)
    run = run.decode('utf-8')
    
    func = lua.eval(r'''
function(integrate, untrusted_code)
    local env = {};
    env.integrate = integrate
    env.print = print
    local untrusted_function, message = load(untrusted_code, nil, 't', env)
    if not untrusted_function then return nil, message end
    debug.sethook(function() error("timeout") end, "", 1e6)
    local success, ret = pcall(untrusted_function)
    debug.sethook()
    return success, ret
end
''')

    def integrate(args: Dict[str, Any]) -> List[Dict[str, Any]]:
        t0 = args['t0']
        y0 = args['y0']
        y0 = (y0[1], y0[2], y0[3])
        tf = args['tf']

        ret = []
        for t, y in climate.integrate(t0=t0, y0=y0, tf=tf):
            # print(f'{t=!r} {y=!r}')
            y = y.tolist()
            ret.append({ 't': t, 'y': y })
        return lua.table_from(ret)

    success, ret = func(integrate, run)
    if not success:
        if not isinstance(ret, Exception):
            ret = Exception(f'{ret!r}')
        raise ret

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

    # print(f'{ret=!r}')
    ret = realize(ret)

    # print(f'{ret=!r}')
    return ret


#--- Functionality


FileLike = NewType('FileLike', Union[BinaryIO, PathLike, str])

# SEC = 0
PRS = 0
LNG = 1
LAT = 2

Sec = NewType('Sec', float)
Prs = NewType('Prs', float)
Lng = NewType('Lng', float)
Lat = NewType('Lat', float)

Val = NewType('Val', float)


def _calculate_ghost_wraparound(points: Tuple[float, ...], *, lo, hi) -> Tuple[float, float]:
    """Calculate the positions for the ghost regions, from simple wraparound.

    >>> _calculate_ghost_wraparound((0.0, 357.5), lo=0.0, hi=360.0)
    (-2.5, 360.0)
    >>> _calculate_ghost_wraparound((-88.7, 88.7), lo=-90.0, hi=90.0)
    (-91.3, 91.3)

    """
    LO, HI = lo, hi
    lo, hi = points[0], points[-1]

    # Assume: LO=0 HI=360 lo=0.0 hi=357.5
    # We want the newly added lo to be 0.0-((360-357.5)+(0-0.0)) lo-((HI-hi)+(LO-lo))
    # We want the newly added hi to be 357.5+(357.5-360)+(0.0-0)

    lo, hi = LO - (HI - hi), HI - (LO - lo)

    return lo, hi
    


@dataclass
class Data:
    multiplier: Optional[float]
    points: Tuple[np.ndarray, ...]
    values: np.ndarray
    interpolator: Interpolator

    @classmethod
    def from_file(cls, fileobj: FileLike, *, multiplier: Optional[float]=None) -> Data:
        with ExitStack() as stack:
            if isinstance(fileobj, str) or isinstance(fileobj, PathLike):
                fileobj = stack.enter_context(open(fileobj, 'rb'))

            def read(format):
                return struct.unpack(format, fileobj.read(struct.calcsize(format)))

            name, = read('4s')
            assert name in (b'UGRD', b'VGRD', b'VVEL'), \
                f'Unexpected name: {name!r}'

            dimensions, = read('I')
            assert dimensions == 4

            sec_count, = read('I')
            sec_points = read(sec_count * 'f')

            prs_count, = read('I')
            prs_points = read(prs_count * 'f')

            lng_count, = read('I')
            lng_points = read(lng_count * 'f')

            lat_count, = read('I')
            lat_points = read(lat_count * 'f')

            lng_point_lo, lng_point_hi = _calculate_ghost_wraparound(lng_points, lo=0.0, hi=360.0)
            lat_point_lo, lat_point_hi = _calculate_ghost_wraparound(lat_points, lo=-90.0, hi=90.0)

            values = np.zeros((sec_count, prs_count, 1+lng_count+1, 1+lat_count+1), dtype=np.float32, order='C')

            lng_points = (lng_point_lo,) + lng_points + (lng_point_hi,)
            lat_points = (lat_point_lo,) + lat_points + (lat_point_hi,)

            points = (sec_points, prs_points, lng_points, lat_points)

            shape = (sec_count, prs_count, lng_count, lat_count)
            chunks, chunk_shape = shape[0], shape[1:]
            for chunk in range(chunks):
                values[chunk, :, 1:-1, 1:-1] = np.fromfile(fileobj, dtype=np.float32, count=np.prod(chunk_shape)).reshape(chunk_shape)

            values[:, :, 0-(0), :] = values[:, :, -2, :]
            values[:, :, 0-(1), :] = values[:, :, +1, :]
            values[:, :, :, 0-(0)] = values[:, :, :, -2]
            values[:, :, :, 0-(1)] = values[:, :, :, +1]

#             values = np.memmap(fileobj, dtype=np.float32, mode='r', offset=offset, shape=shape, order='C')

            interpolator = Interpolator(
                points=points,
                values=values,
                method='linear',
                bounds_error=False,
                fill_value=None,
            )

            return cls(
                multiplier=multiplier,
                points=points,
                values=values,
                interpolator=interpolator,
            )

    def __call__(self, t: Sec, x: Tuple[Prs, Lng, Lat]) -> Val:
        x = np.vstack((t, x)).T
        y = self.interpolator(x)
        if self.multiplier is not None:
            y *= self.multiplier
        return y


@dataclass
class Climate:
    ugrd: Data
    vgrd: Data
    vvel: Data

    @classmethod
    def from_files(cls, *, ugrd: FileLike, vgrd: FileLike, vvel: FileLike) -> Climate:
        ugrd = Data.from_file(ugrd)
        vgrd = Data.from_file(vgrd)
        vvel = Data.from_file(vvel)

        return cls(
            ugrd=ugrd,
            vgrd=vgrd,
            vvel=vvel,
        )

    def __call__(self, t: Sec, x: Tuple[Prs, Lng, Lat]) -> Tuple[Val, Val, Val]:
        ugrd: Val = self.ugrd(t, x)
        vgrd: Val = self.vgrd(t, x)
        vvel: Val = self.vvel(t, x)
        
        return (ugrd, vgrd, vvel)

    def integrate(self,
        *,
        t0: Sec,
        y0: Tuple[Prs, Lng, Lat],
        tf: Sec,
    ) -> Iterator[Tuple[Sec, Tuple[Prs, Lng, Lat]]]:
        _1_DAY_IN_SECONDS = 60 * 60 * 24

        y0 = np.array(y0)

        integrator = Integrator(
            fun=self,
            t0=t0,
            y0=y0,
            t_bound=tf,
            max_step=_1_DAY_IN_SECONDS,
            vectorized=True,
        )

        while True:
            message = integrator.step()
            if message is not None:
                print(f'{message = }')

            t = integrator.t
            y = integrator.y

            if y[PRS] < 0: break
            y[y[LNG] < 0.0] += 360.0
            y[y[LNG] > 360.0] -= 360.0
            y[y[LAT] < -90.0] += 180.0
            y[y[LAT] > 90.0] -= 180.0

            yield t, y

            if integrator.status != 'running':
                break


def main():
    root = Path(__file__).parent.parent / 'data'

    climate = Climate.from_files(
        ugrd=root / 'UGRD-144x73.dat',
        vgrd=root / 'VGRD-144x73.dat',
        vvel=root / 'VVEL-144x73.dat',
    )

    start = time.time()
    n = 0
    for i in range(128):
        prs = random.uniform(10.0, 1000.0)
        lng = random.uniform(0.0, 360.0)
        lat = random.uniform(-90.0, 90.0)

        for (prs, lng, lat) in climate.integrate(
            t0=13.37,
            y0=(prs, lng, lat),
            tf=60 * 60 * 24 * 10,
        ):
            print(f'{prs=} {lng=} {lat=}')
            n += 1

    end = time.time()

    print(f'{n} iterations took {end-start} seconds ({(end-start)/n} seconds/iteration)')


def cli():
    import argparse

    parser = argparse.ArgumentParser()
    args = vars(parser.parse_args())

    main(**args)


if __name__ == '__main__':
    cli()
