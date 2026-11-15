# Statistical hypotheses behind the |i⟩-distillation figures

This note lists every statistical assumption `femoco_figures.ipynb` makes when it turns Monte-Carlo simulation results for our protocol
into the estimates, intervals and fits of the figures and tables used in the Femoco paper. 

**Everything is basically standard here** but we liked the idea of making assumptions explicit. 
For each one the note says what is assumed,
why it holds here, and where it is used. What is not specific to our physical setting (definitions, theorems) is stated in
the docstrings of `distillation_simu/common/statistics.py`. This note covers how these results apply to our data.


We work in the probabilistic setting for our resource-state preparation protocol introduced in the Femoco paper App B.b. Our Monte-Carlo simulation results are interpreted as statistical estimators.

## Notation

Each shot ends in one of three ways: rejected, accepted and correct, or accepted
and failed. A shot is *accepted* when the decoder predicts every
acceptance check correctly, and it *fails* when the decoder then mispredicts the magic state.

| symbol | meaning |
|---|---|
| $N_\mathrm{shot}$ | shots simulated at one point $(d_c, d_r, k, p_z)$, pooled over every job and folder |
| $N_\mathrm{acc}$ | shots accepted (every acceptance check passed) |
| $N_f$ | accepted shots whose produced resource state has a logical error ("failures") |
| $a = N_\mathrm{acc}/N_\mathrm{shot}$ | estimated acceptance rate |
| $p = \mathcal{P}(\text{fail} \mid \text{accepted})$ | logical error rate (LER), the main quantity to estimate |
| $\hat p = N_f/N_\mathrm{acc}$ | its estimate |
| $\mathrm{CL} = 0.95$, $\alpha = 1-\mathrm{CL}$ | confidence level and its complement |
| $p_z$ | physical phase-flip probability of the noise model |
| $d_c$, $d_r$, $k$ | colour-code distance, repetition-code distance, repetition-code preparatory cycles |
| $A$, $b$ | prefactor and exponent of a fitted power law $p = A\,p_z^{\,b}$ |
| $\tau$ | rate of a fitted acceptance law $a = e^{-\tau p_z}$ |


## Hypotheses

**H0. Sinter simulations** We used sinter to run our simulations and resorted to no other optimisation strategies. In particular, no stratified sampling was used: the results are obtained by basic, parallelised Monte-Carlo simulations.

**H1. Real decoder.**  Both verdicts are the decoder's (tesseract, so $p$ is the
failure rate of the circuit *and* its decoder. This defines what is measured; it makes no claim that the
decoder is optimal.

**H2. Shots are independent and identically distributed.** Sinter compiles a fresh stim sampler for each
batch, with no seed, so stim seeds it from system entropy. Batches are therefore independent, and pooling
jobs and folders (`result_counts.load_counts`) adds independent samples of one experiment. "One experiment" is
enforced, not assumed: every folder carries a `simulation_manifest.lock` that fingerprints each point's
detector error model, decoder and readout, so counts are only pooled across runs that simulated the same
thing. 

Under H2 the
three counts (rejected, accepted and correct) are multinomial. Conditioning on the observed $N_\mathrm{acc}$ makes $N_f \sim \mathrm{Binomial}(N_\mathrm{acc}, p)$
*exactly*, so the randomness of $N_\mathrm{acc}$ needs no correction. $\hat p$ is unbiased, with variance
$p(1-p)/N_\mathrm{acc}$.

**H3. Poisson approximation.** The intervals for $p$ were computed assuming $N_f$ follows a Poisson law with mean
$\mu = N_\mathrm{acc}\,p$. This is a standard approximation (Poisson paradigm), made valid by the fact that $p$ is very low but $N_\mathrm{acc}\,p$ is neither large nor small. This rule of thumbs is usually backed up by the Poisson limit theorem, or by its standard refinement, the Le Cam inequality. A further refinement of the latter, obtained by Barbour and Hall [1, Thm. 1], bounds the total-variation distance between the two laws by
$(1-e^{-\mu})\,p$ (in our assumptions). For us, this means that every probability computed with the Poisson approximation is off by at most $(1-e^{-\mu})\,p \leq p$, which is acceptable for our purposes.

**H4. Computing the interval on $p$** (on every LER figure and table).
- When $N_f \ge 1$: exact Poisson confidence interval (central Garwood interval [2]). Its two ends are $\mu_{\pm}/N_\mathrm{acc}$, where $\mu_{\pm}$ are the Poisson limits on $\mu$ at one-sided level $1-\alpha/2$ [3, §40.4.2.3].
- When $N_f = 0$: only an upper bound, with no need for a Poisson approximation, as the exact binomial formula yields $1-\alpha^{1/N_\mathrm{acc}}$. The usual "rule of three" approximates this to $3.00/N_\mathrm{acc}$ [3, Table 40.3]. On the figures, points with $N_f=0$ are drawn as bounds with a downward arrow.

Remark: in the tables, we quote the "95\% upper bounds", which are implicitly one-sided. For the $N_f\geq 1$ points, they thus lie just below the top of the 95\% two sided intervals in the plots (as the 5\% are distributed on top and below for the intervals).


These bounds have a natural frequentist interpretation due to Neyman: over repeated experiments, the interval contains the true $p$ with
probability *at least* CL, see [3, §40.4.2 and §40.4.2.4].

**H5. Computing the interval on the acceptance** (acceptance figures). This is the Wald interval
$a \pm 1.96\sqrt{a(1-a)/N_\mathrm{shot}}$, i.e. the Gaussian approximation to the binomial. It is reliable when
$N_\mathrm{shot}\,a$ and $N_\mathrm{shot}(1-a)$ are both large [4]. Here both counts, accepted and rejected,
exceed $3\times10^6$ at every point. 

**H6. About power-law fits** (slope figure, the extrapolated table row). This is ordinary least squares of
$y = \log \hat p$ against $x = \log p_z$, which estimates $b$ and $\log A$. Ordinary least squares is the best linear unbiased
estimator under the Gauss–Markov hypotheses [5, ch. 3], which are:
- *the model is right*: it assumes $p = A\,p_z^{\,b}$ exactly over the fitted range. In our case, it is rather asymptotic in $p_z \to 0$, and the
  local slopes kept in `PowerLawFit.segments` show how far it holds;
- *$x$ is known exactly*: true, since $p_z$ is an input;
- *the errors are uncorrelated with mean zero*: errors are indeed uncorrelated since points are independent runs (H2), but there is a bias coming from the bias of $\log \hat p$. More precisely, a second order expansion of $E(\log(\hat{p}))$ yields $\log p - 1/(2E(N_f))$, so the mean error is $O(1/N_f)$. This is ok if enough failures have been found, but **completely compromises the fit** when $N_f$ is too small;
- *the errors have equal variance*: this is here **false**. Ordinary Least Square is still unbiased but no longer minimum-variance.

Points with $N_f=0$ are excluded, since $\log 0$ is undefined and they are bounds, not values. The quoted ± on
$b$ is one standard error, $\hat\sigma_b$, which is meaningful under the hypotheses above plus Gaussian
errors (which is not a 95% interval).

**H7. About acceptance fits** (acceptance-vs-$p_z$ figure, τ table). The ansatz is $a = e^{-\tau p_z}$. It holds if
each fault location independently triggers rejection with a probability proportional to $p_z$, so that
$a = \prod_i (1 - c_i p_z) \approx e^{-p_z \sum_i c_i}$. While this approximation is an equality at the level of detector error models, we here make the assumption that the presence of the detector does not disturb this. Moreover, $a = 1$ at $p_z = 0$ because
the noiseless circuit is deterministic. τ is then fitted by unweighted least squares through the origin on
$\log a$: $\hat\tau = -\sum p_z \log a \,/\, \sum p_z^2$. Note that for high values of $d_c=9$, we took the liberty of extrapolating the fit to $p_z$ regimes where no data was measured.

## Limitations

- **Systematic error.** The noise model, the decoder's approximations and the circuit itself are inputs.
  The intervals measure shot noise only.
- **Simultaneous coverage.** Each interval covers its own point at 95% independently. As we plotted $m$ points, about $m/20$ of our intervals are expected to have missed.

## References

1. A. D. Barbour and P. Hall, "On the rate of Poisson convergence", *Math. Proc. Camb. Phil. Soc.* **95**,
   473–480 (1984).
2. F. Garwood, "Fiducial limits for the Poisson distribution", *Biometrika* **28**, 437–442 (1936),
   doi:10.1093/biomet/28.3-4.437.
3. S. Navas *et al.* (Particle Data Group), *Phys. Rev. D* **110**, 030001 (2024), ch. 40 "Statistics"
   (G. Cowan).
4. L. D. Brown, T. T. Cai and A. DasGupta, "Interval estimation for a binomial proportion", *Statist. Sci.*
   **16**, 101–133 (2001), doi:10.1214/ss/1009213286.
5. G. A. F. Seber and A. J. Lee, *Linear Regression Analysis*, 2nd ed., Wiley (2003).
