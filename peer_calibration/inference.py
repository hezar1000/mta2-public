from tqdm import tqdm
import scipy
from scipy import stats
import numpy as np


# minimum bin probability to avoid -infinity log likelihoods
epsilon = 1e-16
alpha_uniform  = 0.05
num_bins = 6

def get_clamp_masks(clamped_variables, num_graders, num_assignments, num_components):

    # Initialize to default masks of correct shapes
    mask_shapes = {
        'true_grades': (1, num_assignments, num_components),
        'efforts': (num_graders, 1, 1),
        'reliabilities': (num_graders, 1, 1),
        'responsibilities': (num_graders, num_assignments, 1)
    }
    ret = {key: np.ma.masked_invalid(np.full(mask_shapes[key], np.nan, dtype=np.float)) for key in mask_shapes}

    # Replace with real values, if present
    for key in mask_shapes:
        if key not in clamped_variables or clamped_variables[key] is None:
            continue
        clamped_floats = np.array(clamped_variables[key], dtype=np.float)
        ret[key] = np.ma.masked_invalid(clamped_floats).reshape(mask_shapes[key])

    return (
        ret['true_grades'], ret['efforts'], ret['reliabilities'], ret['responsibilities']
    )


def set_up_initial_point(hyperparams, num_graders, num_assignments, num_components, initial_point, verbose=False):
    """
    Utility function: get initial point for EM and Gibbs and reshape to correct shapes
    """

    if initial_point is None:
        if verbose:
            print('No initial point provided; using prior means')
        (mu_s, _, alpha_e, beta_e, alpha_rel, beta_rel, _) = hyperparams
        # True grades are row vector
        true_grades = np.full((1, num_assignments, num_components), mu_s)
        # Reliabilities and efforts are column vectors 
        reliabilities = (alpha_rel/beta_rel).reshape(num_graders, 1, 1)
        efforts = np.full((num_graders, 1, 1), alpha_e/(alpha_e+beta_e))

    else:
        if verbose:
            print('Starting from provided initial point')
        (true_grades, efforts, reliabilities) = initial_point
        true_grades = true_grades.reshape(1, num_assignments, num_components)
        reliabilities = reliabilities.reshape(num_graders, 1, 1)
        efforts = efforts.reshape(num_graders, 1, 1)

    return true_grades, reliabilities, efforts

# mapping from reported grades to (left edge, right edge)
def generate_bins(bin_centers, left_edge, right_edge):
    bins = {}
    for i in range(len(bin_centers)):
        if i == 0:
            bin_left_edge = left_edge
        else:
            bin_left_edge = (bin_centers[i-1] + bin_centers[i]) / 2

        if i+1 == len(bin_centers):
            bin_right_edge = right_edge
        else:
            bin_right_edge = (bin_centers[i] + bin_centers[i+1]) / 2 
        bins[bin_centers[i]] = (bin_left_edge, bin_right_edge)
    return bins

# Mapping from grade scale to bin definitions
grade_bin_lookup = {
    '5': generate_bins([0, 1, 2, 3, 4, 5], -20, 20),
    '25': generate_bins([0, 6.25, 12.5, 16.25, 20, 25], -100, 100)
}

# grids to use for true grade and reliability grid-based updates
true_grade_grids = {
    '5': np.linspace(0, 6, 101),
    '25': np.linspace(0, 30, 101)
}

reliability_grids = {
    '5': np.linspace(0, 10, 101)[1:],
    '25': np.linspace(0, 2, 101)[1:],
}

# number of samples to use for true grade and reliability sample-based updates
# TODO: make these hyperparameters?
default_true_grade_samples = 100
default_reliability_samples = 100

def convert_to_bins(reported_grades, grade_scale):
    def get_lower_edge(reported_grade):
        return grade_bin_lookup[grade_scale][reported_grade][0]

    def get_upper_edge(reported_grade):
        return grade_bin_lookup[grade_scale][reported_grade][1]

    left_edges = np.vectorize(get_lower_edge)(reported_grades)
    right_edges = np.vectorize(get_upper_edge)(reported_grades)
    return left_edges, right_edges

def norm_cdf(x, mean, precision):
    # equivalent to scipy.stats.norm.cdf(x, mean, 1/np.sqrt(precision))
    x_transformed = np.sqrt(precision) * (x - mean)
    return scipy.special.ndtr(x_transformed)  
    # return 1/2 * np.exp(x_transformed) * (x_transformed < 0) + (1 - 1/2 * np.exp(-x_transformed)) * (x_transformed >= 0)

def sample_categorical(x, p):
    """
    Sample from each row of x according to p
    
    Inputs: 
    - x: n-dimensional matrix of possible values for x
    - p: n-dimensional matrix of probabilities for each sample; p.sum(axis=-1) must be all-1s
    
    Outputs:
    - (n-1)-dimensional array of samples
    """

    # Convert x and p to 2D
    shape_2D = (np.prod(x.shape[:-1]), x.shape[-1])
    x_2D = x.reshape(shape_2D)
    p_2D = p.reshape(shape_2D)

    # Sample from each row
    p_cumulative = np.cumsum(p_2D, axis=1)
    quantiles = np.random.uniform(size=len(p_2D))
    samples = [x_2D[row, np.searchsorted(p_cumulative[row], quantiles[row])] for row in range(len(p_2D))]
    # samples = [np.random.choice(x[row], p=p[row]) for row in range(len(x))]
    return np.array(samples).reshape(x.shape[:-1])

def convert_ll_to_prob(log_likelihoods):
    """
    Convert unnormalized log-likelihoods to probabilities

    Inputs:
    - log_likelihoods: n-dimensional matrix of log-likelihoods

    Outputs:
    - n-dimensional matrix of probabilities; sum across final dimension is always equal to 1
    """
    scaled_likelihoods = log_likelihoods - np.max(log_likelihoods, axis=-1, keepdims=True)
    p_unnorm = np.exp(scaled_likelihoods)
    return p_unnorm / p_unnorm.sum(axis=-1, keepdims=True)

def reported_grade_log_likelihoods(lower_edges, upper_edges, mask, true_grades, reliabilities, effort_draws, mu_s, tau_l):
    """
    Find the log likelihood of every (bin, true grade, reliability, effort draw).

    Inputs:
    - lower_edges: matrix containing left edge of every reported grade's bin
    - upper_edges: matrix containing right edge of every reported grade's bin
    - mask: (graders, assignments, components, samples) matrix indicating which likelihoods to compute 
            (1 = compute; 0 = ignore) 
    - true_grades: matrix of true grades
    - reliabilities: matrix of reliabilities
    - effort_draws: matrix of effort draws
    - mu_s: true grade mean hyperparameter
    - tau_l: low effort precision hyperparameter

    Note that the mask input must be full dimension; all other inputs only need to broadcast to mask's shape

    Outputs:
    - matrix of likelihoods, same shape as mask. Equal to 0 wherever mask = 0. 
    """
    means = effort_draws * true_grades + (1 - effort_draws) * mu_s
    precisions = effort_draws * reliabilities + (1 - effort_draws) * tau_l

    mask_idx = np.where(mask)    
    means_flat = np.broadcast_to(means, mask.shape)[mask_idx]
    precisions_flat = np.broadcast_to(precisions, mask.shape)[mask_idx]
    lower_edges_flat = np.broadcast_to(lower_edges, mask.shape)[mask_idx]
    upper_edges_flat = np.broadcast_to(upper_edges, mask.shape )[mask_idx]
    
    cdf_lbs = norm_cdf(lower_edges_flat, means_flat, precisions_flat)
    cdf_ubs = norm_cdf(upper_edges_flat, means_flat, precisions_flat)
    
    # Terrible hack for having a uniform distribution
    uniform_probability = 1/num_bins
    # bin_probabilities = cdf_ubs - cdf_lbs + epsilon

    bin_probabilities = alpha_uniform * uniform_probability + (1 - alpha_uniform) * (cdf_ubs - cdf_lbs + epsilon)

    lls = np.zeros(mask.shape) 
    lls[mask_idx] = np.log(bin_probabilities)
    return lls

def sample_true_grades(lower_edges, upper_edges, graph, reliabilities, effort_draws, mu_s, sigma_s, tau_l, grid=None):
    """
    Return a new sample of the true grade matrix.

    Inputs:
    - lower_edges: (graders, assignments, components) matrix with left edge of each reported grade bin
    - upper_edges: (graders, assignments, components) matrix with right edge of each reported grade bin
    - graph: (graders, assignments, 1) matrix indicating which grades are truly reported
    - reliabilities: (graders, 1, 1) matrix of reliabilities
    - effort_draws: (graders, assignments, 1) matrix of effort draws
    - mu_s: true grade mean hyperparameter
    - tau_l: low effort precision hyperparameter
    - use_grid: grid to sample from; if None, consider samples from prior

    Outputs:
    - (1, assignments, components) matrix of true grades
    """
    (num_graders, num_assignments, num_components) = lower_edges.shape
    num_samples = len(grid) if grid is not None else default_true_grade_samples
    full_shape = (num_graders, num_assignments, num_components, num_samples)
    graph_samples = np.broadcast_to(graph[:, :, :, np.newaxis], full_shape).astype(bool)

    if grid is not None:
        true_grade_samples = np.tile(grid, (1, num_assignments, num_components, 1))
        reported_lls = reported_grade_log_likelihoods(
            lower_edges[:, :, :, np.newaxis],
            upper_edges[:, :, :, np.newaxis],
            graph_samples,
            true_grade_samples,
            reliabilities[:, :, :, np.newaxis],
            effort_draws[:, :, :, np.newaxis],
            mu_s,
            tau_l,
        ) * graph_samples
        prior_lls = np.tile(
            scipy.stats.norm.logpdf(grid, mu_s, sigma_s), 
            (1, num_assignments, num_components, 1)
        )
        true_grade_lls = reported_lls.sum(axis=0, keepdims=True) + prior_lls
#         print(reported_lls[graph[:, 17, 0] == 1, 17, -1])

    else:
        true_grade_samples = stats.norm.rvs(
            mu_s, scale=sigma_s, size=(1, num_assignments, num_components, default_true_grade_samples)
        )
        reported_lls = reported_grade_log_likelihoods(
            lower_edges[:, :, :, np.newaxis],
            upper_edges[:, :, :, np.newaxis],
            graph_samples,
            true_grade_samples,
            reliabilities[:, :, :, np.newaxis],
            effort_draws[:, :, :, np.newaxis],
            mu_s,
            tau_l,
        ) * graph_samples
        true_grade_lls = reported_lls.sum(axis=0, keepdims=True)

    true_grade_probabilities = convert_ll_to_prob(true_grade_lls)
    true_grades = sample_categorical(
        true_grade_samples, true_grade_probabilities
    )
    return true_grades

def sample_reliabilities(lower_edges, upper_edges, graph, true_grades, effort_draws, mu_s, alpha_rel, beta_rel, tau_l, grid=None):
    """
    Return a new sample of the reliability matrix.

    Inputs:
    - lower_edges: (graders, assignments, components) matrix with left edge of each reported grade bin
    - upper_edges: (graders, assignments, components) matrix with right edge of each reported grade bin
    - graph: (graders, assignments, 1) matrix indicating which grades are truly reported
    - true_grades: (1, assignments, components) matrix of true grades
    - effort_draws: (graders, assignments, 1) matrix of effort draws
    - mu_s: true grade mean hyperparameter
    - alpha_rel, beta_rel: reliability hyperparameters
    - tau_l: low effort precision hyperparameter
    - grid: grid to sample from; if None, consider samples from prior

    Outputs:
    - (graders, 1, 1) matrix of reliabilities

    TODO: previous implementation had:

        grade_errors = (observed_grades - true_grades)**2
        if max_error is not None:
           grade_errors = np.minimum(grade_errors, max_error**2)

    Is there an equivalent here to avoid wrecking a student's reliability with one very bad grade?
    Maybe mixing in some amount of uniform distribution with their true grade reported distribution?
    (This is effectively what epsilon does already!)
    """

    (num_graders, num_assignments, num_components) = lower_edges.shape
    num_samples = len(grid) if grid is not None else default_reliability_samples
    full_shape = (num_graders, num_assignments, num_components, num_samples)

    graph_samples = np.broadcast_to(graph[:, :, :, np.newaxis], full_shape).astype(bool)
    
    if grid is not None:
        reliability_samples = np.tile(grid, (num_graders, 1, 1, 1))
        reported_lls = reported_grade_log_likelihoods(
            lower_edges[:, :, :, np.newaxis],
            upper_edges[:, :, :, np.newaxis],
            graph_samples,
            true_grades[:, :, :, np.newaxis],
            reliability_samples,
            effort_draws[:, :, :, np.newaxis],
            mu_s,
            tau_l,
        ) * graph_samples
        prior_lls = scipy.stats.gamma.logpdf(
            grid.reshape(1, 1, 1, -1), 
            alpha_rel.reshape(-1, 1, 1, 1), 
            scale=1/beta_rel.reshape(-1, 1, 1, 1)
        )
        reliability_lls = reported_lls.sum(axis=(1, 2), keepdims=True) + prior_lls

    else:
        # TODO: does this work correctly with alpha_rel, beta_rel lists (of length num_graders)
        reliability_samples = stats.gamma.rvs(
            alpha_rel.reshape(num_graders, 1, 1, 1), 
            scale=1/beta_rel.reshape(num_graders, 1, 1, 1), 
            size=(num_graders, 1, 1, default_reliability_samples)
        )
        reported_lls = reported_grade_log_likelihoods(
            lower_edges[:, :, :, np.newaxis],
            upper_edges[:, :, :, np.newaxis],
            graph_samples,
            true_grades[:, :, :, np.newaxis],
            reliability_samples,
            effort_draws[:, :, :, np.newaxis],
            mu_s,
            tau_l,
        ) * graph_samples
        reliability_lls = reported_lls.sum(axis=(1, 2), keepdims=True)

    reliability_probabilities = convert_ll_to_prob(reliability_lls)
    reliabilities = sample_categorical(
        reliability_samples, reliability_probabilities
    )

    return reliabilities

def sample_effort_draws(lower_edges, upper_edges, graph, true_grades, reliabilities, efforts, mu_s, tau_l):
    """
    Return a new sample of the effort draw matrix.

    Inputs:
    - lower_edges: (graders, assignments, components) matrix with left edge of each reported grade bin
    - upper_edges: (graders, assignments, components) matrix with right edge of each reported grade bin
    - graph: (graders, assignments, 1) matrix indicating which grades are truly reported
    - true_grades: (1, assignments, components) matrix of true grades
    - reliabilities: (graders, 1, 1) matrix of reliabilities
    - efforts: (graders, 1, 1) matrix of efforts
    - mu_s: true grade mean hyperparameter
    - tau_l: low effort precision hyperparameter

    Outputs:
    - (graders, 1, 1) matrix of reliabilities

    (note: uses "grid" approach rather than "sampling" approach because effort draw grid only has 2 values)
    """

    (num_graders, num_assignments, num_components) = lower_edges.shape

    effort_draw_samples = np.stack([
        np.full((num_graders, num_assignments, 1), 0),
        np.full((num_graders, num_assignments, 1), 1),
    ], axis=3)
    full_shape = (num_graders, num_assignments, num_components, 2)
    graph_samples = np.broadcast_to(graph[:, :, :, np.newaxis], full_shape).astype(bool)

    reported_lls = reported_grade_log_likelihoods(
        lower_edges[:, :, :, np.newaxis],
        upper_edges[:, :, :, np.newaxis],
        graph_samples,
        true_grades[:, :, :, np.newaxis],
        reliabilities[:, :, :, np.newaxis],
        effort_draw_samples,
        mu_s,
        tau_l,
    ) * graph_samples
    with np.errstate(divide='ignore'): # don't worry about log(0) issues
        prior_ll = np.log(np.stack([
            1 - efforts,
            efforts
        ], axis=3))

    effort_draw_lls = reported_lls.sum(axis=2, keepdims=True) + prior_ll
    effort_draw_probabilities = convert_ll_to_prob(effort_draw_lls)
    effort_draw_probabilities_positive = effort_draw_probabilities[:, :, :, 1] * graph
    effort_draws = stats.bernoulli.rvs(effort_draw_probabilities_positive).reshape(num_graders, num_assignments, 1)
    return effort_draws


def run_gibbs(
    reported_grades, graph, hyperparams, 
    initial_point=None, clamped_values={}, max_error=None, num_samples=1000,
    use_grid=True, save_effort_draws=False, grade_scale='5', verbose=True,
):
    """
    Inputs:
    - reported_grades: num_graders x num_assignments x num_components matrix of grades
    - graph: num_graders x num_assignments matrix: 1 if grader v graded assignment u; 0 otherwise
    - hyperparams: tuple of (mu_s, sigma_s, alpha_e, beta_e, alpha_rel, beta_rel, tau_l)
      (note that alpha_rel and beta_rel can be np.ndarray or float)
    - initial_point: tuple of (true grades array, effort array, reliability array), or None to use prior means
    - clamped_values: dict of values to clamp. See get_clamp_masks() for format
    - max_error: maximum error (in points) used in reliability updates. No limit if None (default)
    - num_samples: number of Gibbs samples to take
    - use_grid: if True, use grid-based sampler; else, use prior-based sampler
    - save_effort_draws: if True, record samples of effort draws 
    - grade_scale: selects bin edges and grids for true grades/reliabilities
    - verbose: if True, show progress bar
    """

    # Convert reported grades
    reported_grades = np.array(reported_grades, dtype=np.float)
    (num_graders, num_assignments, num_components) = reported_grades.shape

    # Cast reported grades as floats
    reported_lower_edges, reported_upper_edges = convert_to_bins(reported_grades, grade_scale)
    
    # Unpack + process hyperparams
    (mu_s, sigma_s, alpha_e, beta_e, alpha_rel, beta_rel, tau_l) = hyperparams
    tau_s = 1 / sigma_s**2

    # Backward compatibility, if alpha_rel and beta_rel are numbers, fill (num_graders) list of constants
    if type(alpha_rel) in [float, int]:
        alpha_rel = np.full(num_graders, alpha_rel)
    if type(beta_rel) in [float, int]:
        beta_rel = np.full(num_graders, beta_rel)

    # Set up initial point
    true_grades, reliabilities, efforts = set_up_initial_point(
        (mu_s, sigma_s, alpha_e, beta_e, alpha_rel, beta_rel, tau_l), 
        num_graders, 
        num_assignments, 
        num_components, 
        initial_point
    )
    effort_draws = np.full((num_graders, num_assignments, 1), 1.0)
    graph = graph.reshape(num_graders, num_assignments, 1)

    # Get masks for clamped values
    (true_grades_clamped, efforts_clamped, reliabilities_clamped, effort_draws_clamped) = get_clamp_masks(
        clamped_values, num_graders, num_assignments, num_components    
    )

    # Get grids 
    true_grade_grid = true_grade_grids[grade_scale] if use_grid else None
    reliability_grid = reliability_grids[grade_scale] if use_grid else None

    # Set up return values: index by (sample number, grader/assignment number, component number [for true grades])
    ret_true_grades = np.zeros((num_samples, num_assignments, num_components))
    ret_efforts = np.zeros((num_samples, num_graders))
    ret_reliabilities = np.zeros((num_samples, num_graders))
    if save_effort_draws:
        ret_effort_draws = np.zeros((num_samples, num_graders, num_assignments))

    for t in tqdm(range(num_samples), disable=not verbose):
        # Sample effort draws for each assignment
        effort_draws = sample_effort_draws(
            reported_lower_edges, reported_upper_edges, graph, true_grades, reliabilities, efforts, mu_s, tau_l
        )
        effort_draws[~effort_draws_clamped.mask] = effort_draws_clamped[~effort_draws_clamped.mask]

        # Sample true grades
        if np.count_nonzero(~np.isnan(clamped_values['true_grades'].sum(axis=1))) == reported_grades.shape[1] :
            true_grades[~true_grades_clamped.mask] = true_grades_clamped[~true_grades_clamped.mask]
        else: 
            true_grades = sample_true_grades(
            reported_lower_edges, reported_upper_edges, graph, reliabilities, effort_draws, mu_s, sigma_s, tau_l, true_grade_grid
        )
            true_grades[~true_grades_clamped.mask] = true_grades_clamped[~true_grades_clamped.mask]

        # Sample efforts
        efforts_alpha = alpha_e + (graph * effort_draws).sum(axis=1, keepdims=True)
        efforts_beta = beta_e + (graph * (1 - effort_draws)).sum(axis=1, keepdims=True)
        efforts = stats.beta.rvs(efforts_alpha, efforts_beta, size=(num_graders, 1, 1))
        efforts[~efforts_clamped.mask] = efforts_clamped[~efforts_clamped.mask]

        # Sample reliabilities
        reliabilities = sample_reliabilities(
            reported_lower_edges, reported_upper_edges, graph, true_grades, effort_draws, mu_s, alpha_rel, beta_rel, tau_l, reliability_grid
        )
        reliabilities[~reliabilities_clamped.mask] = reliabilities_clamped[~reliabilities_clamped.mask]

        # Save samples
        ret_true_grades[t, :, :] = true_grades.reshape(num_assignments, num_components)
        ret_efforts[t, :] = efforts.flatten()
        ret_reliabilities[t, :] = reliabilities.flatten()
        if save_effort_draws:
            ret_effort_draws[t, :, :] = effort_draws.reshape(num_graders, num_assignments)  
        
    # TODO: put these in a dataclass?
    if save_effort_draws:
        ret = (
            ret_true_grades, 
            ret_efforts, 
            ret_reliabilities, 
            ret_effort_draws
        )
    else:
        ret = (
            ret_true_grades, 
            ret_efforts, 
            ret_reliabilities, 
        )
    return ret
