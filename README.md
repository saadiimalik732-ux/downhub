# DownHub — Cloudflare Containers

This is the corrected Cloudflare Workers Builds project for DownHub.

The Cloudflare Worker routes requests to a Linux Container running:
- Flask
- yt-dlp
- FFmpeg
- Node.js runtime for yt-dlp's YouTube JavaScript support

Cloudflare Containers is a Workers Paid feature. Containers require a full Linux environment and are appropriate for this workload.

Workers Builds:
- Build command: leave empty
- Deploy command: `npx wrangler deploy`
- Root directory: `/`

Important:
- The Dockerfile targets linux/amd64 as required by Cloudflare Containers.
- `enableInternet = true` is required because the container must contact YouTube.
- Container disk is ephemeral. This project provides a temporary download link from the same running container; it is not permanent storage.
- For a public service, add rate limiting/authentication and a clear acceptable-use policy.
- Download only content you have permission to download.

Current Cloudflare docs:
https://developers.cloudflare.com/containers/guides/deploy/
https://developers.cloudflare.com/containers/get-started/
