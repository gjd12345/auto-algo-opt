import numpy as np

def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    harmonic_mean = 2.0 / (1.0 / (item + 1e-9) + 1.0 / (residual + 1e-9))
    sigmoid_derivative = np.exp(-harmonic_mean) / (1.0 + np.exp(-harmonic_mean)) ** 2
    sinc_penalty = np.abs(np.sinc(residual / (item + 1e-9)))  # sinc interference
    index_decay = np.tanh(np.arange(len(bins), 0, -1) / len(bins))
    scores = sigmoid_derivative - 0.2 * sinc_penalty + 0.1 * index_decay
    return scores
