import numpy as np
from line_profiler import LineProfiler


def euclidean_broadcast(x, y):
    """Euclidean square distance matrix.

    Inputs:
    x: (N, m) numpy array
    y: (N, m) numpy array

    Ouput:
    (N, N) Euclidean square distance matrix:
    r_ij = (x_ij - y_ij)^2
    """
    diff = x[:, np.newaxis, :] - y[np.newaxis, :, :]

    return (diff * diff).sum(axis=2)


if __name__ == "__main__":
    nsamples = 2000
    nfeat = 50
    rng = np.random.default_rng()
    x = 10. * rng.random((nsamples, nfeat))

    lp = LineProfiler()
    lp(euclidean_broadcast)(x, x)
    lp.print_stats()
