#!/bin/sh
cd "$(dirname "$0")"
exec ./cloudflared tunnel --url http://127.0.0.1:3000
