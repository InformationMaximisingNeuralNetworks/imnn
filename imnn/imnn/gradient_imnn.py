import jax
import jax.numpy as np
from imnn.imnn._imnn import _IMNN
from imnn.utils import value_and_jacrev
from imnn.utils.utils import _check_input


class GradientIMNN(_IMNN):
    """Information maximising neural network fit using known derivatives

    The outline of the fitting procedure is that a set of :math:`i\\in[1, n_s]`
    simulations :math:`{\\bf d}^i` originally generated at fiducial model
    parameter :math:`{\\bf\\theta}^\\rm{fid}`, and their derivatives
    :math:`\\partial{\\bf d}^i/\\partial\\theta_\\alpha` with respect to model
    parameters are used. The fiducial simulations, :math:`{\\bf d}^i`, are
    passed through a network to obtain summaries, :math:`{\\bf x}^i`, and the
    jax automatic derivative of these summaries with respect to the inputs are
    calculated :math:`\\partial{\\bf x}^i\\partial{\\bf d}^j\\delta_{ij}`. The
    chain rule is then used to calculate

    .. math::
        \\frac{\\partial{\\bf x}^i}{\\partial\\theta_\\alpha} =
        \\frac{\\partial{\\bf x}^i}{\\partial{\\bf d}^j}
        \\frac{\\partial{\\bf d}^j}{\\partial\\theta_\\alpha}

    With :math:`{\\bf x}^i` and
    :math:`\\partial{{\\bf x}^i}/\\partial\\theta_\\alpha` the covariance

    .. math::
        C_{ab} = \\frac{1}{n_s-1}\sum_{i=1}^{n_s}(x^i_a-\mu^i_a)(x^i_b-\mu^i_b)

    and the derivative of the mean of the network outputs with respect to the
    model parameters

    .. math::
        \\frac{\\partial\\mu_a}{\\partial\\theta_\\alpha} = \\frac{1}{n_d}
        \\sum_{i=1}^{n_d}\\frac{\\partial{x^i_a}}{\\partial\\theta_\\alpha}

    can be calculated and used form the Fisher information matrix

    .. math::
        F_{\\alpha\\beta} = \\frac{\\partial\\mu_a}{\\partial\\theta_\\alpha}
        C^{-1}_{ab}\\frac{\\partial\\mu_b}{\\partial\\theta_\\beta}.

    The loss function is then defined as

    .. math::
        \\Lambda = -\\log|{\\bf F}| + r(\\Lambda_2) \\Lambda_2

    Since any linear rescaling of a sufficient statistic is also a sufficient
    statistic the negative logarithm of the determinant of the Fisher
    information matrix needs to be regularised to fix the scale of the network
    outputs. We choose to fix this scale by constraining the covariance of
    network outputs as

    .. math::
        \\Lambda_2 = ||{\\bf C}-{\\bf I}|| + ||{\\bf C}^{-1}-{\\bf I}||

    Choosing this constraint is that it forces the covariance to be
    approximately parameter independent which justifies choosing the covariance
    independent Gaussian Fisher information as above. To avoid having a dual
    optimisation objective, we use a smooth and dynamic regularisation strength
    which turns off the regularisation to focus on maximising the Fisher
    information when the covariance has set the scale

    .. math::
        r(\\Lambda_2) = \\frac{\\lambda\\Lambda_2}{\\Lambda_2-\\exp
        (-\\alpha\\Lambda_2)}.

    Once the loss function is calculated the automatic gradient is then
    calculated and used to update the network parameters via the optimiser
    function.

    Parameters
    ----------
    fiducial : float(n_s, input_shape)
        The simulations generated at the fiducial model parameter values used
        for calculating the covariance of network outputs (for fitting)
    derivative : float(n_d, input_shape, n_params)
        The derivative of the simulations with respect to the model parameters
        (for fitting)
    validation_fiducial : float(n_s, input_shape) or None
        The simulations generated at the fiducial model parameter values used
        for calculating the covariance of network outputs (for validation)
    validation_derivative : float(n_d, input_shape, n_params) or None
        The derivative of the simulations with respect to the model parameters
        (for validation)
    """
    def __init__(self, n_s, n_d, n_params, n_summaries, input_shape, θ_fid,
                 model, optimiser, key_or_state, fiducial, derivative,
                 validation_fiducial=None, validation_derivative=None):
        """Constructor method

        Initialises all IMNN attributes, constructs neural network and its
        initial parameter values and creates history dictionary. Also fills the
        simulation attributes (and validation if available).

        Parameters
        ----------
        n_s : int
            Number of simulations used to calculate summary covariance
        n_d : int
            Number of simulations used to calculate mean of summary derivative
        n_params : int
            Number of model parameters
        n_summaries : int
            Number of summaries, i.e. outputs of the network
        input_shape : tuple
            The shape of a single input to the network
        θ_fid : float(n_params,)
            The value of the fiducial parameter values used to generate inputs
        model : tuple, len=2
            Tuple containing functions to initialise neural network
            ``fn(rng: int(2), input_shape: tuple) -> tuple, list`` and the
            neural network as a function of network parameters and inputs
            ``fn(w: list, d: float(None, input_shape)) -> float(None, n_summari
            es)``.
            (Essentibly stax-like, see `jax.experimental.stax <https://jax.read
            thedocs.io/en/stable/jax.experimental.stax.html>`_))
        optimiser : tuple, len=3
            Tuple containing functions to generate the optimiser state
            ``fn(x0: list) -> :obj:state``, to update the state from a list of
            gradients ``fn(i: int, g: list, state: :obj:state) -> :obj:state``
            and to extract network parameters from the state
            ``fn(state: :obj:state) -> list``.
            (See `jax.experimental.optimizers <https://jax.readthedocs.io/en/st
            able/jax.experimental.optimizers.html>`_)
        key_or_state : int(2) or :obj:state
            Either a stateless random number generator or the state object of
            an preinitialised optimiser
        fiducial : float(n_s, input_shape)
            The simulations generated at the fiducial model parameter values
            used for calculating the covariance of network outputs
            (for fitting)
        derivative : float(n_d, input_shape, n_params)
            The derivative of the simulations with respect to the model
            parameters (for fitting)
        validation_fiducial : float(n_s, input_shape) or None, default=None
            The simulations generated at the fiducial model parameter values
            used for calculating the covariance of network outputs
            (for validation)
        validation_derivative : float(n_d, input_shape, n_params) or None
            The derivative of the simulations with respect to the model
            parameters (for validation)
        """
        super().__init__(
            n_s=n_s,
            n_d=n_d,
            n_params=n_params,
            n_summaries=n_summaries,
            input_shape=input_shape,
            θ_fid=θ_fid,
            model=model,
            key_or_state=key_or_state,
            optimiser=optimiser)
        self._set_data(fiducial, derivative, validation_fiducial,
                       validation_derivative)

    def _set_data(self, fiducial, derivative, validation_fiducial,
                  validation_derivative):
        """Checks and sets data attributes with the correct shape

        Parameters
        ----------
        fiducial : float(n_s, input_shape)
            The simulations generated at the fiducial model parameter values
            used for calculating the covariance of network outputs
            (for fitting)
        derivative : float(n_d, input_shape, n_params)
            The derivative of the simulations with respect to the model
            parameters (for fitting)
        validation_fiducial : float(n_s, input_shape) or None, default=None
            The simulations generated at the fiducial model parameter values
            used for calculating the covariance of network outputs
            (for validation). Sets ``validate = True`` attribute if provided
        validation_derivative : float(n_d, input_shape, n_params) or None
            The derivative of the simulations with respect to the model
            parameters (for validation). Sets ``validate = True`` attribute if
            provided
        """
        self.fiducial = _check_input(
            fiducial, (self.n_s,) + self.input_shape, "fiducial")
        self.derivative = _check_input(
            derivative, (self.n_d,) + self.input_shape + (self.n_params,),
            "derivative")
        if ((validation_fiducial is not None)
                and (validation_derivative is not None)):
            self.validation_fiducial = _check_input(
                validation_fiducial, (self.n_s,) + self.input_shape,
                "validation_fiducial")
            self.validation_derivative = _check_input(
                validation_derivative,
                (self.n_d,) + self.input_shape + (self.n_params,),
                "validation_derivative")
            self.validate = True

    def get_summaries(self, w, key=None, validate=False):
        """Gets all network outputs and derivatives wrt model parameters

        Selects either the fitting or validation sets and passes them through
        the network to get the network outputs.

        Parameters
        ----------
        w : list or None, default=None
            The network parameters if wanting to calculate the Fisher
            information with a specific set of network parameters
        key : int(2,) or None, default=None
            A random number generator for generating simulations on-the-fly
        validate : bool, default=False
            Whether to get summaries of the validation set

        Returns
        -------
        float(n_s, n_summaries):
            The set of all network outputs used to calculate the covariance
        float(n_d, n_summaries, n_params):
            The derivative of the network ouputs wrt the model parameters

        Methods
        -------
        get_derivatives:
            Calculates the jacobian of the network output and its value
        """
        def get_derivatives(simulation):
            """Calculates the jacobian of the network output and its value

            Parameters
            ----------
            simulation: float(input_shape)
                The fiducial simulation to calculate the Jacobian of

            Returns
            -------
            float(n_summaries):
                The network output (summary) of the simulation
            float(input_shape, n_summaries):
                The derivative of the network outputs wrt the inputs
            """
            x, dx_dd = value_and_jacrev(self.model, argnums=1)(w, simulation)
            return x, dx_dd.T

        if validate:
            fiducial = self.validation_fiducial
            derivative = self.validation_derivative
        else:
            fiducial = self.fiducial
            derivative = self.derivative
        if self.n_d < self.n_s:
            summaries, dx_dd = jax.vmap(get_derivatives)(fiducial[:self.n_d])
            summaries = np.vstack([
                summaries,
                self.model(w, fiducial[self.n_d:])])
        else:
            summaries, dx_dd = jax.vmap(get_derivatives)(fiducial)
        return summaries, np.einsum("i...j,i...k->ijk", dx_dd, derivative)
