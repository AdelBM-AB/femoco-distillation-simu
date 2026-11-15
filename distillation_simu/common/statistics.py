from __future__ import annotations

"""Content

- ``poisson_upper_limit`` / ``poisson_lower_limit``: exact one-sided confidence limits on a Poisson mean,
  given one observed count. Combined, they give the central (Garwood) interval.
- ``PowerLawFit`` / ``fit_power_law``: ``y = A * x**b`` by ordinary least squares on ``(log x, log y)``.

Notation used throughout:

- ``n``: an observed count, a realisation of ``N ~ Poisson(mu)``, with ``mu > 0`` the unknown mean;
- ``CL``: a confidence level and ``alpha = 1 - CL``. We will assume 0 < alpha < 1/2
- ``m``: the number of points in a fit;
- ``A``, ``b``: the prefactor and exponent of a power law.

Standard facts only. The module does not know where its counts come from. How this project turns
Monte-Carlo shots into Poisson counts, and which hypotheses that requires, is set out in
``output/figures/femoco_paper/statistical_hypotheses.md``.

References:

- [PDG] S. Navas et al. (Particle Data Group), PRD 110, 030001 (2024), ch.40 "Statistics" 
    https://pdg.lbl.gov/2024/reviews/rpp2024-rev-statistics.pdf.
- [DLMF] NIST Digital Library of Mathematical Functions, https://dlmf.nist.gov, eqs. 8.4.9-8.4.10.
- [Choi] K. P. Choi, Proc. Amer. Math. Soc. 121, 245-251 (1994): the median of Poisson(mu) lies in
  ``[mu - ln 2, mu + 1/3)``.
- [SL] G. A. F. Seber and A. J. Lee, *Linear Regression Analysis*, 2nd ed., Wiley (2003), ch. 3.
"""



import dataclasses
import math
from typing import Optional, Sequence, Tuple

import numpy as np


def poisson_upper_limit(nb_events: int, confidence: float) -> float:
    """The exact one-sided upper confidence limit ``mu_up`` on a Poisson mean, given ``n = nb_events``.

    **Definition** (Neyman construction, by inverting a one-sided test [PDG §40.4.2.3]).
    ``mu_up`` is the largest mean at which seeing ``n`` or fewer events still has probability
    ``alpha``::

        P(N <= n; mu_up) = alpha,   P(N <= n; mu) = sum_{j=0}^{n} e^{-mu} mu^j / j!

    Any larger ``mu`` makes the observation an event of probability below ``alpha``, so it is rejected.

    **Coverage.** For every true ``mu``, ``P(mu_up(N) >= mu) >= CL``. The inequality is strict in
    general because ``N`` is discrete, so the limit is conservative.

    **Facts the computation relies on.**

    - ``P(N <= n; mu)`` decreases strictly in ``mu``, so the root is unique and bisection finds it.
    - The Poisson-Gamma identity, ``P(N <= n; mu) = Q(n+1, mu)`` (regularised upper incomplete gamma,
      [DLMF 8.4.10]), gives the closed form ``mu_up = chi2.ppf(CL, 2n + 2) / 2``. It is written out
      here rather than taken from scipy, to avoid a further dependency.
    - At ``n = 0``: ``mu_up = -ln(alpha)``, i.e. 3.00 at ``CL = 0.95``. At ``n`` = 1, 3, 10 it is 4.74, 7.75, 16.96.
    - The bisection starts from the bracket ``[n, n + 1]`` and doubles the top. That needs
      ``P(N <= n; mu = n) > alpha``. It holds for ``CL > 1/2``, since ``n`` is the median of Poisson(n) [Choi].

    **Bayesian reading.** The posterior on ``mu`` under a flat prior is Gamma(n + 1, 1). By the same
    identity, its CL-quantile is exactly ``mu_up`` [PDG §40.4.1]. This coincidence holds for the one-sided
    *upper* limit only.

    Returns a mean count. Divide by the number of trials for a rate.
    """
    alpha = 1 - confidence
    if nb_events == 0:
        return -math.log(alpha)

    def cdf(lam: float) -> float:  # P(N <= nb_events; mu = lam)
        return sum(math.exp(k * math.log(lam) - lam - math.lgamma(k + 1))
                   for k in range(nb_events + 1))

    low, high = float(nb_events), float(nb_events) + 1.0
    while cdf(high) > alpha:
        high *= 2
    for _ in range(200):
        mid = (low + high) / 2
        if cdf(mid) > alpha:
            low = mid
        else:
            high = mid
    return (low + high) / 2


def poisson_lower_limit(nb_events: int, confidence: float) -> float:
    """The exact one-sided lower confidence limit ``mu_low`` on a Poisson mean, given ``n = nb_events``.

    **Definition.** The mirror image of ``poisson_upper_limit``. ``mu_low`` is the smallest mean at which
    seeing ``n`` or more events still has probability ``alpha``::

        P(N >= n; mu_low) = alpha

    The upper tail rises strictly in ``mu``, which again makes bisection valid. In closed form
    ``mu_low = chi2.ppf(alpha, 2n) / 2``, the alpha-quantile of Gamma(n, 1) [DLMF 8.4.9]. At ``n = 0``
    it is 0: no mean is excluded from below. The bracket ``[0, n]`` needs ``P(N >= n; mu = n) > alpha``,
    true for ``CL > 1/2`` [Choi].

    **Coverage.** ``P(mu_low(N) <= mu) >= CL`` for every true ``mu``.

    **Central interval.** ``[poisson_lower_limit(n, 1 - alpha/2), poisson_upper_limit(n, 1 - alpha/2)]``
    is the Garwood interval at level ``CL``, with ``alpha/2`` in each tail. At ``n = 0`` its top is 3.69
    at 95%, against 3.00 for the one-sided limit. Unlike the upper limit, the lower limit has no
    flat-prior Bayesian counterpart: uniform-prior lower limits undercover [PDG §40.4.2.4].

    Returns a mean count.
    """
    alpha = 1 - confidence
    if nb_events == 0:
        return 0.0

    # P(N >= nb_events; mu = lam), as 1 minus the lower sum. That subtraction loses relative precision
    # once the tail is near machine epsilon, which only happens far beyond any count this project sees.
    def tail(lam: float) -> float:
        return 1 - sum(math.exp(k * math.log(lam) - lam - math.lgamma(k + 1)) for k in range(nb_events))

    low, high = 0.0, float(nb_events)
    for _ in range(200):
        mid = (low + high) / 2
        if tail(mid) < alpha:
            low = mid
        else:
            high = mid
    return (low + high) / 2


@dataclasses.dataclass(frozen=True)
class PowerLawFit:
    """A fitted ``y = A * x**b`` (``prefactor`` = A, ``exponent`` = b), from ``fit_power_law``.

    - ``exponent_stderr``: the estimated standard error of the slope, ``sigma_b``. It is one standard
      deviation, *not* a confidence interval: a ``CL`` interval is ``b +- t_{m-2, (1+CL)/2} * sigma_b``
      (Student-t with ``m - 2`` degrees of freedom), under Gaussian errors [SL]. ``None`` when
      ``m = 2``: the line then passes through both points, and with zero residual degrees of freedom
      the error cannot be estimated (it is undefined, not zero).
    - ``segments``: the slope between each pair of consecutive points, ``(x_low, x_high, slope)``. A
      global fit assumes one exponent for the whole range. Segments that drift show where that fails,
      which a single number hides. This project has also long quoted exponents as such segment slopes.
    """

    exponent: float
    prefactor: float
    exponent_stderr: Optional[float]
    segments: Tuple[Tuple[float, float, float], ...]  # (pz_low, pz_high, slope)

    def __str__(self) -> str:
        err = "" if self.exponent_stderr is None else f" +- {self.exponent_stderr:.2f}"
        drift = ", ".join(f"{lo:.1e}->{hi:.1e}: {s:.2f}" for lo, hi, s in self.segments)
        return (f"{self.prefactor:.3g} * pz**{self.exponent:.2f}{err}   [segments: {drift}]")


def fit_power_law(pz: Sequence[float], logical_error: Sequence[float]) -> PowerLawFit:
    """Fit ``y = A * x**b`` by ordinary least squares (OLS) in log-log.

    With ``x = pz`` and ``y = logical_error``, the model is linear in the logs. For points
    ``i = 1..m``::

        Y_i = beta_0 + b * X_i + eps_i,   X_i = log x_i,   Y_i = log y_i,   A = exp(beta_0)

    **Estimators.** With ``Xbar``, ``Ybar`` the sample means and ``S_xx = sum (X_i - Xbar)^2``::

        b_hat   = sum (X_i - Xbar)(Y_i - Ybar) / S_xx,     beta0_hat = Ybar - b_hat * Xbar
        s^2     = RSS / (m - 2),                           RSS = sum (Y_i - beta0_hat - b_hat X_i)^2
        sigma_b = sqrt(s^2 / S_xx)

    **Hypotheses and what each one buys** [SL ch. 3]:

    - H1, linearity: ``E[eps_i] = 0``, i.e. the power law is exact over the fitted range;
    - H2, fixed regressors: the ``X_i`` are known without error;
    - H3, uncorrelated errors: ``Cov(eps_i, eps_j) = 0`` for ``i != j``;
    - H4, homoscedasticity: ``Var(eps_i) = sigma^2``, the same for every point;
    - H5, normality: ``eps_i ~ N(0, sigma^2)``.

    Under H1-H2, ``b_hat`` and ``beta0_hat`` are unbiased. Under H1-H4, the Gauss-Markov theorem makes
    them the best linear unbiased estimators, ``s^2`` is unbiased for ``sigma^2``, and
    ``Var(b_hat) = sigma^2 / S_xx``, so ``sigma_b`` estimates its standard deviation. H5 is needed only to
    turn ``sigma_b`` into an exact interval (Student-t, see ``PowerLawFit``).

    If H4 fails, OLS stays unbiased but is no longer minimum-variance, and ``sigma_b`` is no longer
    a consistent estimate of its error. Weighted least squares, with weights ``1/Var(eps_i)``, restores
    both. This fit is unweighted: it is the right estimator only when the points are equally precise.

    ``A_hat = exp(beta0_hat)`` is consistent but biased, since ``E[exp(.)] != exp(E[.])``.

    Raises ``ValueError`` on mismatched or non-1-D inputs, on fewer than two points, and on any
    ``y <= 0``, where ``log y`` is undefined.
    """
    pz_array = np.asarray(pz, dtype=float)
    ler_array = np.asarray(logical_error, dtype=float)
    if pz_array.shape != ler_array.shape or pz_array.ndim != 1:
        raise ValueError(f"pz and logical_error must be one-dimensional and the same length, got "
                         f"{pz_array.shape} and {ler_array.shape}")
    if pz_array.size < 2:
        raise ValueError(f"a slope needs at least two points, got {pz_array.size}")
    # In this project a zero LER is a point that collected no failures (a "starved" point, see the
    # results-and-analysis skill): an upper bound, not a value. It must be dropped or given more shots,
    # never fitted. That is also why the fit is unweighted: the Poisson weight of a point is its failure
    # count N_f, since Var(log LER_hat) ~ 1/N_f, which is zero exactly where the data are least checked.
    starved = np.flatnonzero(ler_array <= 0)
    if starved.size:
        raise ValueError(
            f"logical error rate is {ler_array[starved[0]]} at pz={pz_array[starved[0]]:.3g}. A "
            f"zero here is a point that collected no failures, not a measurement of zero -- check "
            f"its raw counts and either give it more shots or drop it from the fit."
        )

    order = np.argsort(pz_array)
    x, y = np.log(pz_array[order]), np.log(ler_array[order])
    slope, intercept = np.polyfit(x, y, 1)  # b_hat, beta0_hat

    stderr: Optional[float] = None
    if x.size > 2:  # sigma_b = sqrt(RSS / (m - 2) / S_xx)
        residuals = y - (slope * x + intercept)
        variance = float(residuals @ residuals) / (x.size - 2)
        stderr = float(np.sqrt(variance / float(((x - x.mean()) ** 2).sum())))

    segments = tuple(
        (float(pz_array[order][i]), float(pz_array[order][i + 1]),
         float((y[i + 1] - y[i]) / (x[i + 1] - x[i])))
        for i in range(x.size - 1)
    )
    return PowerLawFit(exponent=float(slope), prefactor=float(np.exp(intercept)),
                       exponent_stderr=stderr, segments=segments)
