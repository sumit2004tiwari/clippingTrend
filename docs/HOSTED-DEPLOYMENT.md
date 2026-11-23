# Deploying the fastclipping studio

The default configuration permits the desktop studio only on the computer running it. A hosted request has a remote address, so the old phone gate returned `Phone access is off on this computer.` Enabling phone mode alone does not enable the desktop studio.

## Hosted studio settings

Set these environment variables in your hosting dashboard or service environment:

```text
FASTCLIPPING_WEB=1
FASTCLIPPING_WEB_USERNAME=studio
FASTCLIPPING_WEB_PASSWORD=<your own random password of at least 16 characters>
NEONCLIPPING_LAN=0
NEONCLIPPING_NO_AUTOUPDATE=1
```

Replace the password placeholder; do not commit actual credentials. Use your host's HTTPS domain. Opening the website will show the browser's username/password prompt. These are studio credentials you set above, separate from a phone PIN or payment key. All authenticated visitors operate the same studio and share its files and settings; this is a private operator deployment, not independent customer accounts.

Install the Python dependencies from `requirements.txt`, and install FFmpeg and FFprobe on the server. Run this command from the directory containing `app.py`:

```sh
python app.py
```

In hosted mode this binds to `0.0.0.0` and uses the hosting provider's `PORT` environment variable, falling back to `NEONCLIPPING_PORT` or `8770`. For a host that requires an explicit ASGI command, use:

```sh
python -m uvicorn app:app --host 0.0.0.0 --port "$PORT" --workers 1
```

The second command assumes your Linux host supplies `PORT`; use a numeric port such as `8770` if it does not. Keep one worker and one instance because processing state is held in memory. Behind Nginx on the same VPS, bind Uvicorn to `127.0.0.1` instead and proxy to it. Hosted authentication applies even to loopback requests, so proxy address rewriting cannot bypass the login.

Configure the health check path as `/healthz`. It returns only `{"ok":true}` without a login when hosted credentials are configured. Missing credentials, a username containing `:`, or a password shorter than 16 characters result in HTTP 503 until the environment is fixed.

Attach persistent storage and set `NEONCLIPPING_DATA_DIR` to its absolute path. Otherwise a hosting restart or replacement may lose uploads, clips and settings. Use a server with sufficient CPU, RAM and disk for FFmpeg and speech transcription; static hosting cannot run this backend.

Redeploy or restart the service after updating the code and environment. Confirm that `/` asks for credentials, the correct credentials load the studio, and unauthenticated `/queue`, `/upload` and `/media/...` requests remain blocked. The existing Wi-Fi phone mode is unchanged when `FASTCLIPPING_WEB` is absent or `0`.

This is an alternative to the separate Nginx authentication setup in the earlier deployment PDF. When using app-managed authentication, configure these variables and forward the `Authorization` header to Uvicorn. Use one authentication layer with the intended credentials; a proxy configured with different Basic credentials will otherwise prevent signing in.

References: [FastAPI HTTP Basic authentication](https://fastapi.tiangolo.com/advanced/security/http-basic-auth/) and [Uvicorn settings](https://uvicorn.dev/settings/).
