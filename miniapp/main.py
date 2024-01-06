#
# CSCS-USI SummerSchool miniapp ported to Python
#
#   A small benchmark app that solves the 2D fisher equation using second-order
#   finite differences.
#
#   Originally developed in C++ by Ben Cumming, CSCS
#   Ported to Python by Vasileios Karakasis, CSCS

import collections
import matplotlib
import numba
import numpy as np
import os
import sys
from datetime import datetime

import linalg
import operators


Discretization = collections.namedtuple(
    'Discretization', ['nx', 'ny', 'N', 'nt', 'dt', 'dx', 'alpha']
)

Boundary = collections.namedtuple(
    'Boundary', ['north', 'south', 'east', 'west']
)

NewtonStatus = collections.namedtuple(
    'NewtonStatus', ['solution', 'converged', 'timestep',
                     'iters_newton', 'iters_cg', 'status_cg']
)


def usage():
    print(f'Usage: {sys.argv[0]} nx ny nt t', file=sys.stderr)
    print(f'  nx  number of gridpoints in x-direction', file=sys.stderr)
    print(f'  ny  number of gridpoints in y-direction', file=sys.stderr)
    print(f'  nt  number of timesteps', file=sys.stderr)
    print(f'  t   total simulated time', file=sys.stderr)


def parse_arg(v, argname, fn):
    try:
        v = fn(v)
    except ValueError as e:
        print(f'{sys.argv[0]}: could not parse argument {argname}: {e}')
        usage()
        sys.exit(1)

    return v


@numba.njit(cache=True)
def timeloop(x, boundary, options, max_cg_iters, max_newton_iters, tolerance):
    # main timeloop

    nx, ny = options.nx, options.ny

    # initialize fields
    b = np.zeros(nx*ny)
    deltax = np.zeros(nx*ny)

    nt = options.nt
    iters_newton = 0
    iters_cg = 0

    for timestep in range(1, nt+1):
        x_old = np.copy(x)
        converged = False
        for it in range(max_newton_iters):
            operators.diffusion(x, b, x_old, boundary, options)
            residual = np.sqrt(b @ b)
            if residual < tolerance:
                converged = True
                break

            cg_status = linalg.cg(
                deltax, x_old, b, boundary, options,
                tolerance, max_cg_iters
            )

            iters_cg += cg_status.iters
            if not cg_status.converged:
                break

            x -= deltax

        iters_newton += it + 1
        if not converged:
            break

    return NewtonStatus(x, converged, timestep,
                        iters_newton, iters_cg, cg_status)


def main():
    if len(sys.argv) < 5:
        print(f'{sys.argv[0]}: too few arguments', file=sys.stderr)
        usage()
        sys.exit(1)

    nx, ny, nt, t, *_ = sys.argv[1:]

    def is_positive(x):
        if x <= 0:
            raise ValueError(f'value must be positive: {x}')

        return x

    nx = parse_arg(nx, 'nx', lambda x: is_positive(int(x)))
    ny = parse_arg(ny, 'ny', lambda x: is_positive(int(x)))
    nt = parse_arg(nt, 'nt', lambda x: is_positive(int(x)))
    t  = parse_arg(t,  't',  lambda x: is_positive(float(x)))

    # calculate timestep
    dt = t / nt

    # compute the distance between grid points
    # assume that x dimension has length 1.0
    dx = 1. / (nx - 1)

    # set alpha, assume diffusion coefficient D is 1
    alpha = (dx*dx) / dt

    options = Discretization(nx, ny, nx*ny, nt, dt, dx, alpha)

    # set iteration parameters
    max_cg_iters = 200
    max_newton_iters = 50
    tolerance = 1.e-6

    print(f'========================================================================')
    print(f'                      Welcome to mini-stencil!')
    print(f'version   :: Python')
    print(f'mesh      :: {nx} * {ny} dx = {dx}')
    print(f'time      :: {nt} time steps from 0 .. {nt*dt}')
    print(f'iteration :: CG {max_cg_iters}, Newton {max_newton_iters}, '
          f'tolerance {tolerance}')
    print(f'========================================================================')

    # Solution field
    x = np.zeros(nx*ny)

    # set dirichlet boundary conditions to 0 all around
    bndN  = np.zeros(nx)
    bndS  = np.zeros(nx)
    bndE  = np.zeros(ny)
    bndW  = np.zeros(ny)
    boundary = Boundary(bndN, bndS, bndE, bndW)

    # set the initial condition
    # a circle of concentration 0.1 centred at (xdim/4, ydim/4) with radius
    # no larger than 1/8 of both xdim and ydim
    xspace = np.linspace(0, 1, nx)
    yspace = np.linspace(0, 1, ny)
    X, Y = np.meshgrid(xspace, yspace, indexing='ij')

    xc = 1.0 / 4.0
    yc = (ny - 1) * dx / 4
    radius = min(xc, yc) / 2.0
    x = x.reshape((nx, ny))
    x[(X - xc) ** 2 + (Y - yc) ** 2 < radius * radius] = 0.1

    # restore x_new's shape
    x = x.flatten()

    flops_bc = 0
    flops_diff = 0
    flops_blas1 = 0
    iters_cg = 0
    iters_newton = 0
    timespent = datetime.now()

    status = timeloop(
        x, boundary, options, max_cg_iters, max_newton_iters, tolerance
    )
    if not status.converged:
        cg_status = status.status_cg
        if not cg_status.converged:
            print(f'ERROR: CG failed to converge after {cg_status.iters} '
                  f'iterations, with residual {cg_status.residual}',
                  file=sys.stderr)

        print(f'step {status.timestep} '
              f'ERROR : nonlinear iterations failed to converge',
              file=sys.stderr)

    # get times
    timespent = (datetime.now() - timespent).total_seconds()
    print('----------------------------------------'
          '----------------------------------------')
    print(f'simulation took {timespent} seconds')
    print(f'{status.iters_cg} conjugate gradient iterations, at rate of '
          f'{status.iters_cg/timespent} iters/second')
    print(f'{status.iters_newton} newton iterations')
    print(f'Goodbye!')

    if 'DISPLAY' not in os.environ:
        matplotlib.use('Agg')

    import matplotlib.pyplot as plt

    # number of contours we wish to see
    V = [-0.01, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.01]
    fig = plt.figure()
    ax = fig.add_subplot(111)
    outfile = f'output_{nx}x{ny}_t={t}_steps={nt}.png'

    print(f'generating solution figure in "{outfile}" ...')
    ax.contourf(X, Y, x.reshape((nx, ny)), V, alpha=.75, cmap='jet')
    ax.axes.set_aspect('equal')
    fig.savefig(outfile, dpi=72)

    if 'DISPLAY' in os.environ:
        plt.show()


if __name__ == '__main__':
    main()
