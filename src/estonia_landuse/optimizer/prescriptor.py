"""Neural network prescriptor: maps cell features → target land-use fractions."""

import numpy as np

# Output size: target fractions for [forest, wetland, agriculture, grassland]
N_OUTPUTS = 4  # changeable groups only (urban/water are fixed)


class Prescriptor:
    """Small fixed-topology neural network that outputs target land-use fractions.
    
    Architecture: input → hidden (tanh) → output (softmax → fractions)
    Weights are flat numpy arrays — easy to mutate and crossover.
    """

    def __init__(
        self,
        in_size: int,
        hidden_size: int = 16,
        rng: np.random.Generator | None = None,
    ):
        self.in_size = in_size
        self.hidden_size = hidden_size
        self.out_size = N_OUTPUTS
        
        # Weight shapes
        self.w1_shape = (in_size, hidden_size)
        self.b1_shape = (hidden_size,)
        self.w2_shape = (hidden_size, self.out_size)
        self.b2_shape = (self.out_size,)
        
        # Total parameter count
        self.n_params = (
            in_size * hidden_size + hidden_size +
            hidden_size * self.out_size + self.out_size
        )
        
        # Initialize random weights
        rng = np.random.default_rng() if rng is None else rng
        self.params = rng.standard_normal(self.n_params).astype(np.float32) * 0.1
        
        # Fitness metrics (set by trainer)
        self.metrics = None
        self.rank = None
        self.constraint_violation = None

    def prescribe(self, features: np.ndarray) -> np.ndarray:
        """Given feature matrix (n_cells, in_size), return target fractions (n_cells, 4).
        
        Output columns: [forest_target, wetland_target, agriculture_target, grassland_target]
        Values are non-negative and sum to 1 per cell (will be rescaled to available land by simulator).
        """
        w1, b1, w2, b2 = self._unpack_params()
        
        # Forward pass
        hidden = np.tanh(features @ w1 + b1)
        logits = hidden @ w2 + b2
        
        # Softmax → fractions that sum to 1
        exp_logits = np.exp(logits - logits.max(axis=1, keepdims=True))
        fractions = exp_logits / exp_logits.sum(axis=1, keepdims=True)
        
        return fractions

    def _unpack_params(self):
        """Unpack flat param vector into weight matrices."""
        idx = 0
        w1_size = self.w1_shape[0] * self.w1_shape[1]
        w1 = self.params[idx:idx + w1_size].reshape(self.w1_shape)
        idx += w1_size
        
        b1 = self.params[idx:idx + self.hidden_size]
        idx += self.hidden_size
        
        w2_size = self.w2_shape[0] * self.w2_shape[1]
        w2 = self.params[idx:idx + w2_size].reshape(self.w2_shape)
        idx += w2_size
        
        b2 = self.params[idx:idx + self.out_size]
        return w1, b1, w2, b2

    def copy(self) -> "Prescriptor":
        """Create a copy with same weights."""
        clone = object.__new__(Prescriptor)
        clone.in_size = self.in_size
        clone.hidden_size = self.hidden_size
        clone.out_size = self.out_size
        clone.w1_shape = self.w1_shape
        clone.b1_shape = self.b1_shape
        clone.w2_shape = self.w2_shape
        clone.b2_shape = self.b2_shape
        clone.n_params = self.n_params
        clone.params = self.params.copy()
        clone.metrics = None
        clone.rank = None
        clone.constraint_violation = None
        return clone
