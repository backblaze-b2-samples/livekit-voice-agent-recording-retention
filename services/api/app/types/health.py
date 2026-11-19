from pydantic import Field

from app.types.base import ResponseModel


class HealthStatus(ResponseModel):
    """Liveness plus B2 and LiveKit reachability.

    The route answers HTTP 200 even when a dependency is unreachable, so a
    caller must read the flags rather than trusting the status code.
    """

    status: str = Field(description='"healthy" when B2 answered, else "degraded".')
    b2_connected: bool = Field(
        description="True when the bucket answered a cheap head request."
    )
    livekit_connected: bool = Field(
        description="True when the LiveKit server answered a room list request."
    )
