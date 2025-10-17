"""
Circuit Breaker Pattern Implementation

Protects external services from cascading failures by monitoring error rates
and temporarily blocking requests when thresholds are exceeded.

States:
- CLOSED: Normal operation, requests pass through
- OPEN: Threshold exceeded, requests are blocked
- HALF_OPEN: Testing if service has recovered
"""

import time
from enum import Enum
from typing import Callable, Any, Optional
from datetime import datetime
from config.logging_config import get_logger

logger = get_logger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"       # Normal operation
    OPEN = "open"          # Blocking requests
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open"""
    pass


class CircuitBreaker:
    """
    Circuit breaker implementation with automatic recovery testing.

    The circuit breaker monitors consecutive failures and automatically
    opens when a threshold is exceeded, preventing cascading failures.
    After a timeout period, it enters half-open state to test recovery.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        success_threshold: int = 2,
        name: str = "default"
    ):
        """
        Initialize circuit breaker

        Args:
            failure_threshold: Number of consecutive failures before opening
            recovery_timeout: Seconds to wait before testing recovery
            success_threshold: Consecutive successes needed to close from half-open
            name: Identifier for this circuit breaker
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self.name = name

        # State tracking
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._last_state_change: Optional[float] = None

        # Statistics
        self.total_calls = 0
        self.total_failures = 0
        self.total_successes = 0
        self.times_opened = 0

        logger.info(
            f"Circuit breaker '{name}' initialized: "
            f"failure_threshold={failure_threshold}, "
            f"recovery_timeout={recovery_timeout}s"
        )

    @property
    def state(self) -> CircuitState:
        """Get current state, automatically transitioning to half-open if timeout expired"""
        if self._state == CircuitState.OPEN:
            if self._should_attempt_recovery():
                self._transition_to_half_open()
        return self._state

    def _should_attempt_recovery(self) -> bool:
        """Check if enough time has passed to attempt recovery"""
        if self._last_failure_time is None:
            return False
        return time.time() - self._last_failure_time >= self.recovery_timeout

    def _transition_to_half_open(self) -> None:
        """Transition from OPEN to HALF_OPEN state"""
        logger.info(f"Circuit breaker '{self.name}' transitioning to HALF_OPEN (testing recovery)")
        self._state = CircuitState.HALF_OPEN
        self._success_count = 0
        self._last_state_change = time.time()

    def _transition_to_open(self) -> None:
        """Transition to OPEN state"""
        logger.warning(
            f"Circuit breaker '{self.name}' OPENED after {self._failure_count} consecutive failures"
        )
        self._state = CircuitState.OPEN
        self._last_failure_time = time.time()
        self._last_state_change = time.time()
        self.times_opened += 1

    def _transition_to_closed(self) -> None:
        """Transition to CLOSED state"""
        logger.info(
            f"Circuit breaker '{self.name}' CLOSED after {self._success_count} consecutive successes"
        )
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_state_change = time.time()

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection

        Args:
            func: Function to execute
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Result of function call

        Raises:
            CircuitBreakerError: If circuit is open
            Exception: Any exception raised by the function
        """
        self.total_calls += 1

        # Check if circuit is open
        if self.state == CircuitState.OPEN:
            raise CircuitBreakerError(
                f"Circuit breaker '{self.name}' is OPEN. "
                f"Will retry in {self._get_recovery_time_remaining():.0f}s"
            )

        try:
            # Execute the function
            result = func(*args, **kwargs)
            self._on_success()
            return result

        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self) -> None:
        """Handle successful call"""
        self.total_successes += 1

        if self._state == CircuitState.HALF_OPEN:
            # In half-open, count successes toward closing
            self._success_count += 1
            logger.debug(
                f"Circuit breaker '{self.name}' success {self._success_count}/{self.success_threshold}"
            )

            if self._success_count >= self.success_threshold:
                self._transition_to_closed()

        elif self._state == CircuitState.CLOSED:
            # In closed state, reset failure count on success
            self._failure_count = 0

    def _on_failure(self) -> None:
        """Handle failed call"""
        self.total_failures += 1

        if self._state == CircuitState.HALF_OPEN:
            # In half-open, any failure reopens the circuit
            logger.warning(f"Circuit breaker '{self.name}' failed during recovery test, reopening")
            self._transition_to_open()

        elif self._state == CircuitState.CLOSED:
            # In closed state, count consecutive failures
            self._failure_count += 1
            logger.debug(
                f"Circuit breaker '{self.name}' failure {self._failure_count}/{self.failure_threshold}"
            )

            if self._failure_count >= self.failure_threshold:
                self._transition_to_open()

    def _get_recovery_time_remaining(self) -> float:
        """Get seconds remaining until recovery attempt"""
        if self._last_failure_time is None:
            return 0
        elapsed = time.time() - self._last_failure_time
        return max(0, self.recovery_timeout - elapsed)

    def reset(self) -> None:
        """Manually reset circuit breaker to closed state"""
        logger.info(f"Circuit breaker '{self.name}' manually reset to CLOSED")
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None

    def get_stats(self) -> dict:
        """
        Get circuit breaker statistics

        Returns:
            Dictionary with current state and statistics
        """
        return {
            'name': self.name,
            'state': self.state.value,
            'failure_count': self._failure_count,
            'success_count': self._success_count,
            'total_calls': self.total_calls,
            'total_failures': self.total_failures,
            'total_successes': self.total_successes,
            'times_opened': self.times_opened,
            'last_state_change': datetime.fromtimestamp(self._last_state_change).isoformat() if self._last_state_change else None,
            'recovery_time_remaining': self._get_recovery_time_remaining() if self._state == CircuitState.OPEN else 0,
            'failure_rate_pct': round((self.total_failures / self.total_calls * 100) if self.total_calls > 0 else 0, 2)
        }

    def __repr__(self) -> str:
        return (
            f"CircuitBreaker(name='{self.name}', state={self.state.value}, "
            f"failures={self._failure_count}/{self.failure_threshold})"
        )
