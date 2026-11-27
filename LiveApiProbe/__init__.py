"""Live API Probe: an Ableton Live remote script that reports on Live's API."""

from .probe import LiveApiProbe


def create_instance(c_instance):
    """Live calls this when the control surface is picked in its settings."""
    return LiveApiProbe(c_instance)
