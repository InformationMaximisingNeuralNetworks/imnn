Using the AggregatedNumericalGradientIMNN
=========================================

When we do not have a generative model which we can automatically or
analytically calculate the derivatives of some simulations we have to
resort to numerical methods to calculate the derivatives of the network
outputs with respect to the physical model parameters necessary to fit
an IMNN. To do this we will use seed-matched derivatives,
i.e.┬ásimulations will be made at parameter values above and below the
fiducial for each parameter respectively and using the same seed for
each variation within the pairs. It is important to use seed matching
because this way there is an exact way to separate the effect of
realisation from parameters - many more realisations will be needed and
fitting will be much more difficult without seed matching. Furthermore,
if the simulations are too numerous or too large to fit into memory or
could be accelerated over several devices, we can aggregate the
gradients too. This is an expensive operation and should only be used if
memory over a single device is really an issue. Note that with a fixed
data set for training an IMNN it is important to have a validation set
for early stopping. This is because, with a limited training set there
*will* be accidental correlations which look like they are due to
parameters and the IMNN *will* extract these features. Using a
validation set for early stopping makes sure that once all the features
in the validation set have been extracted then no extra information can
be incorrectly processed.

For this example we are going to summaries the unknown mean,
:math:`\mu`, and variance, :math:`\Sigma`, of :math:`n_{\bf d}=10` data
points of two 1D random Gaussian field,
:math:`{\bf d}=\{d_i\sim\mathcal{N}(\mu,\Sigma)|i\in[1, n_{\bf d}]\}`.
This is an interesting problem since we know the likelihood
analytically, but it is non-Gaussian

.. math:: \mathcal{L}({\bf d}|\mu,\Sigma) = \prod_i^{n_{\bf d}}\frac{1}{\sqrt{2\pi|\Sigma|}}\exp\left[-\frac{1}{2}\frac{(d_i-\mu)^2}{\Sigma}\right]

As well as knowing the likelihood for this problem, we also know what
sufficient statistics describe the mean and variance of the data - they
are the mean and the variance

.. math:: \frac{1}{n_{\bf d}}\sum_i^{n_{\bf d}}d_i = \mu\textrm{  and  }\frac{1}{n_{\bf d}-1}\sum_i^{n_{\bf d}}(d_i-\mu)^2=\Sigma

What makes this an interesting problem for the IMNN is the fact that the
sufficient statistic for the variance is non-linear, i.e.┬áit is a sum of
the square of the data, and so linear methods like MOPED would be lossy
in terms of information.

We can calculate the Fisher information by taking the negative second
derivative of the likelihood taking the expectation by inserting the
relations for the sufficient statistics, i.e.┬áand examining at the
fiducial parameter values

.. math:: {\bf F}_{\alpha\beta} = -\left.\left(\begin{array}{cc}\displaystyle-\frac{n_{\bf d}}{\Sigma}&0\\0&\displaystyle-\frac{n_{\bf d}}{2\Sigma^2}\end{array}\right)\right|_{\Sigma=\Sigma^{\textrm{fid}}}.

Choosing fiducial parameter values of :math:`\mu^\textrm{fid}=0` and
:math:`\Sigma^\textrm{fid}=1` we find that the determinant of the Fisher
information matrix is :math:`|{\bf F}_{\alpha\beta}|=50`.

.. code:: ipython3

    from imnn import AggregatedNumericalGradientIMNN

    import jax
    import jax.numpy as np
    from jax.experimental import stax, optimizers

    import tensorflow as tf

WeÔÇÖre going to use 1000 summary vectors, with a length of two, at a time
to make an estimate of the covariance of network outputs and the
derivative of the mean of the network outputs with respect to the two
model parameters.

.. code:: ipython3

    n_s = 1000
    n_d = n_s

    n_params = 2
    n_summaries = n_params

    input_shape = (10,)

The simulator is simply

.. code:: ipython3

    def simulator(key, ╬Ş):
        return ╬Ş[0] + jax.random.normal(key, shape=input_shape) * np.sqrt(╬Ş[1])

Our fiducial parameter values are :math:`\mu^\textrm{fid}=0` and
:math:`\Sigma^\textrm{fid}=1`. We will vary these values by
:math:`\delta\mu=0.1` and :math:`\delta\Sigma=0.1`.

.. code:: ipython3

    ╬Ş_fid = np.array([0., 1.])
    ╬┤╬Ş = np.array([0.1, 0.1])
    ╬Ş_der = (╬Ş_fid + np.einsum("i,jk->ijk", np.array([-1., 1.]), np.diag(╬┤╬Ş) / 2.)).reshape((-1, 2))

For initialising the neural network a random number generator and weÔÇÖll
grab another for generating the data:

.. code:: ipython3

    rng = jax.random.PRNGKey(0)
    rng, model_key, data_key = jax.random.split(rng, num=3)

WeÔÇÖll make the keys for each of the simulations for fitting and
validation

.. code:: ipython3

    data_keys = np.array(jax.random.split(rng, num=2 * n_s))

.. code:: ipython3

    fiducial = jax.vmap(simulator)(
        data_keys[:n_s],
        np.repeat(np.expand_dims(╬Ş_fid, 0), n_s, axis=0))
    validation_fiducial = jax.vmap(simulator)(
        data_keys[n_s:],
        np.repeat(np.expand_dims(╬Ş_fid, 0), n_s, axis=0))
    numerical_derivative = jax.vmap(simulator)(
        np.repeat(data_keys[:n_s], ╬Ş_der.shape[0], axis=0),
        np.tile(╬Ş_der, (n_s, 1))).reshape(
            (n_s, 2, n_params) + input_shape)
    validation_numerical_derivative = jax.vmap(simulator)(
        np.repeat(data_keys[n_s:], ╬Ş_der.shape[0], axis=0),
        np.tile(╬Ş_der, (n_s, 1))).reshape(
            (n_s, 2, n_params) + input_shape)

WeÔÇÖre going to use ``jax``\ ÔÇÖs stax module to build a simple network
with three hidden layers each with 128 neurons and which are activated
by leaky relu before outputting the two summaries. The optimiser will be
a ``jax`` Adam optimiser with a step size of 0.001.

.. code:: ipython3

    model = stax.serial(
        stax.Dense(128),
        stax.LeakyRelu,
        stax.Dense(128),
        stax.LeakyRelu,
        stax.Dense(128),
        stax.LeakyRelu,
        stax.Dense(n_summaries))
    optimiser = optimizers.adam(step_size=1e-3)

We will use the CPU as the host device and use the GPUs for calculating
the summaries.

.. code:: ipython3

    host = jax.devices("cpu")[0]
    devices = jax.devices("gpu")

Now lets say that we know that we can process 100 simulations at a time
per device before running out of memory, we therefore can set

.. code:: ipython3

    n_per_device = 100

The AggregatedNumericalGradientIMNN can now be initialised setting up
the network and the fitting routine (as well as the plotting function)

.. code:: ipython3

    imnn = AggregatedNumericalGradientIMNN(
        n_s=n_s, n_d=n_d, n_params=n_params, n_summaries=n_summaries,
        input_shape=input_shape, ╬Ş_fid=╬Ş_fid, model=model,
        optimiser=optimiser, key_or_state=model_key, host=host,
        devices=devices, n_per_device=n_per_device, ╬┤╬Ş=╬┤╬Ş,
        fiducial=fiducial, derivative=numerical_derivative,
        validation_fiducial=validation_fiducial,
        validation_derivative=validation_numerical_derivative,
        prefetch=tf.data.AUTOTUNE, cache=True)

To set the scale of the regularisation we use a coupling strength
:math:`\lambda` whose value should mean that the determinant of the
difference between the covariance of network outputs and the identity
matrix is larger than the expected initial value of the determinant of
the Fisher information matrix from the network. How close to the
identity matrix the covariance should be is set by :math:`\epsilon`.
These parameters should not be very important, but they will help with
convergence time.

.. code:: ipython3

    ╬╗ = 10.
    ¤Á = 0.1

Fitting can then be done simply by calling:

.. code:: ipython3

    imnn.fit(╬╗, ¤Á, patience=10, max_iterations=1000, print_rate=1)


Here we have included a ``print_rate`` for a progress bar, but leaving
this out will massively reduce fitting time (at the expense of not
knowing how many iterations have been run). The IMNN will be fit for a
maximum of ``max_iterations = 1000`` iterations, but with early stopping
which can turn on after ``min_iterations = 100`` iterations and after
``patience = 10`` iterations where the maximum determinant of the Fisher
information matrix has not increased. ``imnn.w`` is set to the values of
the network parameters which obtained the highest value of the
determinant of the Fisher information matrix, but the values at the
final iteration can be set using ``best = False``.

To continue training one can simply rerun fit

.. code:: python

   imnn.fit(╬╗, ¤Á, patience=10, max_iterations=1000, print_rate=1)

although we will not run it in this example.

To visualise the fitting history we can plot the results:

.. code:: ipython3

    imnn.plot(expected_detF=50);



.. image:: output_26_0.png
