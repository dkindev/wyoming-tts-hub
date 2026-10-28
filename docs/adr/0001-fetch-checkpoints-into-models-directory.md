# Fetch upstream checkpoints into the Models directory

Upstream checkpoints must be fetched onto the host before a **TTS Engine** can
load them. They are fetched into the configured Models directory rather than a
shared global model cache: operators control and can back up that directory, and
an offline deployment keeps working from what it already holds, at the cost of not
sharing checkpoints with other tools on the same host.
