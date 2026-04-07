"""
woundtrack.exceptions
=====================

Domain-specific exceptions for the woundtrack library.
All exceptions inherit from WoundtrackError for easy catching.
"""

__all__ = [
    "WoundtrackError",
    "MissingT0Error",
    "InvalidMaskError",
    "MissingDataError",
    "InvalidTrajectoryError",
]


class WoundtrackError(Exception):
    """Base exception for all woundtrack errors."""
    pass


class MissingT0Error(WoundtrackError):
    """Raised when a trajectory is missing the baseline (t=0) timepoint."""
    
    def __init__(self, trajectory_key: str = "", message: str = ""):
        self.trajectory_key = trajectory_key
        if message:
            super().__init__(message)
        elif trajectory_key:
            super().__init__(f"Trajectory '{trajectory_key}' is missing t=0 baseline.")
        else:
            super().__init__("Trajectory is missing t=0 baseline.")


class InvalidMaskError(WoundtrackError):
    """Raised when a mask fails validation checks."""
    
    def __init__(self, reason: str = "", trajectory_key: str = "", time: float = 0):
        self.reason = reason
        self.trajectory_key = trajectory_key
        self.time = time
        
        parts = []
        if trajectory_key:
            parts.append(f"trajectory='{trajectory_key}'")
        parts.append(f"t={time}")
        if reason:
            parts.append(reason)
        
        super().__init__(f"Invalid mask ({', '.join(parts)})")


class MissingDataError(WoundtrackError):
    """Raised when required data (image or mask) is missing."""
    
    def __init__(self, field: str = "data", trajectory_key: str = "", time: float = 0):
        self.field = field
        self.trajectory_key = trajectory_key
        self.time = time
        
        msg = f"Missing {field}"
        if trajectory_key:
            msg += f" for trajectory '{trajectory_key}'"
        msg += f" at t={time}"
        
        super().__init__(msg)


class InvalidTrajectoryError(WoundtrackError):
    """Raised when a trajectory structure is invalid."""
    
    def __init__(self, trajectory_key: str = "", reason: str = ""):
        self.trajectory_key = trajectory_key
        self.reason = reason
        
        msg = f"Invalid trajectory"
        if trajectory_key:
            msg += f" '{trajectory_key}'"
        if reason:
            msg += f": {reason}"
        
        super().__init__(msg)
