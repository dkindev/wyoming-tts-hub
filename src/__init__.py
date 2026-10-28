"""Package initialization."""

from importlib.metadata import metadata

__metadata__ = metadata("wyoming-tts-hub")

__project_urls__ = {}
for item in __metadata__.get_all("Project-URL") or []:
    label, url = item.split(",", 1)
    __project_urls__[label.strip()] = url.strip()

PROJECT_NAME = "Wyoming TTS Hub"
"""What the project calls itself, as distinct from what a deployment is called.

An operator names the service they run, and that name is what a client should see and
connect to. It is not what the software is credited to: renaming a service to something
of one's own must not make the server claim the credit. The distribution name is the
other thing this is not — it names the distribution, which is an implementation detail
of how the project is packaged rather than the project itself.
"""

__all__ = ["PROJECT_NAME", "__metadata__", "__project_urls__"]
