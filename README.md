# 2DEXY dashboard

**Earlier dashboard and control-plane implementation**

This public repository contains an earlier 2DEXY dashboard built around an HTML interface, a Flask API and SQLite storage. It is separate from the current **2DEXY Full-Stack** project within Matheria Finance.

## Repository scope

| File | Responsibility |
| --- | --- |
| [index.html](index.html) | Dashboard interface |
| [server.py](server.py) | Flask endpoints, SQLite records and command / status exchange |
| [Dockerfile](Dockerfile) | Container packaging |

The server records signals, observations, trades and status, and exposes a command exchange for a backend control process. These files document an earlier implementation; they are not the current Next.js / Python / Rust Full-Stack source or a verified live-trading release.

## Current project

See the [2DEXY Full-Stack overview](https://github.com/nasrsalman030/nasrsalman030/blob/main/projects/2dexy-fullstack.md) for the current product architecture, engineering focus and evaluation boundaries.

[Matheria and Aetheria portfolio](https://github.com/nasrsalman030)

## Status

Retained for project history and reference. This documentation update does not run or deploy the server and makes no profitability or production-readiness claim.
