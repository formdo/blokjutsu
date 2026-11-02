# Security

Blokjutsu runs MOSS-Image's pipeline code, which is downloaded from Hugging Face together with the model. The
app pins the exact model version it was tested with (`MODEL_REVISIONS` in `blokjutsu/params.py`), so new code
is only run after a Blokjutsu release moves the pin.

To report a security problem, please don't open a public issue. Use GitHub's private vulnerability reporting
(the **Security** tab of this repository, then **Report a vulnerability**). We'll reply as soon as we can.
