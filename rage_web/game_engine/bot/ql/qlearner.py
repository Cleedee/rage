"""Q-Learning linear (semi-gradient) com numpy.

Q(s, a) = θ[a] · φ(s)

Update (Q-learning off-policy):
    θ[a] += α · (r + γ·max_{a'} Q(s', a') − Q(s, a)) · φ(s)

O espaço de ações é fixo (todas as macro-ações); máscaras de
legalidade escondem ações inválidas no momento.
"""

from __future__ import annotations

import os

import numpy as np


class LinearQLearner:
    """Aproximador linear de Q com updates semi-gradient."""

    def __init__(self, n_features: int, n_actions: int,
                 alpha: float = 0.01, gamma: float = 0.95,
                 epsilon: float = 0.3, epsilon_min: float = 0.02,
                 epsilon_decay: float = 0.9995, seed: int | None = None,
                 l2: float = 1e-4):
        self.n_features = int(n_features)
        self.n_actions = int(n_actions)
        self.alpha = alpha
        self.gamma = gamma
        self.epsilon = epsilon
        self.epsilon_min = epsilon_min
        self.epsilon_decay = epsilon_decay
        self.l2 = l2
        self.rng = np.random.default_rng(seed)
        # theta[a] = pesos para cada feature
        self.theta = np.zeros((self.n_actions, self.n_features),
                              dtype=np.float64)
        self.steps = 0

    # ── Consulta ──

    def action_values(self, state: np.ndarray,
                      mask: list[bool] | np.ndarray | None = None) -> np.ndarray:
        """Valores Q para todas as ações (ações mascaradas → -inf)."""
        q = self.theta @ state
        if mask is not None:
            q = q - (~np.asarray(mask, dtype=bool)) * 1e9
        return q

    def choose_action(self, state: np.ndarray,
                      mask: list[bool] | np.ndarray | None = None,
                      greedy: bool = False) -> int:
        """Escolhe ação com ε-greedy respeitando a máscara de legalidade."""
        q = self.action_values(state, mask)
        if not greedy and self.rng.random() < self.epsilon:
            if mask is None:
                return int(self.rng.integers(self.n_actions))
            legal = [i for i, m in enumerate(mask) if m]
            if not legal:
                return int(self.rng.integers(self.n_actions))
            return int(self.rng.choice(legal))
        return int(np.argmax(q))

    # ── Aprendizado ──

    def update(self, s: np.ndarray, a: int, r: float,
               s_next: np.ndarray,
               mask_next: list[bool] | np.ndarray | None = None) -> None:
        """Update Q-learning com bootstrap (estado não-terminal)."""
        q_cur = float(self.theta[a] @ s)
        q_next = float(np.max(self.action_values(s_next, mask_next)))
        target = r + self.gamma * q_next
        delta = target - q_cur
        # Limita a magnitude do erro para estabilidade numérica
        delta = max(-100.0, min(100.0, delta))
        self.theta[a] *= (1.0 - self.alpha * self.l2)
        self.theta[a] += self.alpha * delta * s
        self.steps += 1

    def terminal_update(self, s: np.ndarray, a: int, r: float) -> None:
        """Update com estado terminal (sem bootstrap)."""
        q_cur = float(self.theta[a] @ s)
        delta = max(-100.0, min(100.0, r - q_cur))
        self.theta[a] *= (1.0 - self.alpha * self.l2)
        self.theta[a] += self.alpha * delta * s
        self.steps += 1

    def decay_epsilon(self) -> None:
        self.epsilon = max(self.epsilon_min,
                           self.epsilon * self.epsilon_decay)

    # ── Persistência ──

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        np.savez(path,
                 theta=self.theta,
                 alpha=np.array([self.alpha]),
                 gamma=np.array([self.gamma]),
                 epsilon=np.array([self.epsilon]),
                 epsilon_min=np.array([self.epsilon_min]),
                 epsilon_decay=np.array([self.epsilon_decay]),
                 l2=np.array([self.l2]),
                 steps=np.array([self.steps]))

    def load(self, path: str) -> bool:
        if not os.path.exists(path):
            return False
        data = np.load(path)
        theta = data['theta']
        if theta.shape != self.theta.shape:
            raise ValueError(
                f'Pesos {path} tem shape {theta.shape}, '
                f'mas o learner espera {self.theta.shape}')
        self.theta = theta.astype(np.float64)
        self.alpha = float(data['alpha'][0])
        self.gamma = float(data['gamma'][0])
        self.epsilon = float(data['epsilon'][0])
        self.epsilon_min = float(data['epsilon_min'][0])
        self.epsilon_decay = float(data['epsilon_decay'][0])
        self.steps = int(data['steps'][0])
        if 'l2' in data:
            self.l2 = float(data['l2'][0])
        return True
