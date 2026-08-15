# Alex + Sarah Projects

## OPEN THE PROJECT HOME

https://maaronfanberg-lab.github.io/me-/

Tap that link to open the launcher with Resonator and the other current projects.

## Current launcher

- Resonator
- Harmonograph
- Attractor Lab
- OMEF-A Attractor
- OMEF Total-State Prototype
- OMEF FULL
- Geo Pulse

## Claude simulator access

This repo now includes a project-level MCP server in `mcp_server.py` plus `.mcp.json` configuration for Claude Code.

When the repo is opened in Claude Code, approve the project MCP server `alex-repo-simulator` when prompted. Claude can then call the simulator directly with tools for:

- simulator information
- single simulation runs
- batches across several scales
- latest result inspection
- recent run history
- loading a specific saved run

Example request to Claude:

> Use alex-repo-simulator. Start with a small Monte Carlo run, inspect the result, then try several scales and tell me what changes.

The MCP layer wraps the existing `scripts/cluster_worker.py` and `scripts/aggregate_cluster.py` simulator rather than replacing them. Local run history is stored in `.simulator_runs/` and is intentionally ignored by Git.

## Native iPhone projects

- Macro Focus — near-biased autofocus camera for tiny subjects, targeting iPhone 6 / iOS 12+. Source: `apps/macro-focus-ios/`

This repository is the permanent home base for our runnable experiments. GitHub Pages is already enabled for the web projects. Native iPhone projects live here as source code and must be built/signed as iOS apps rather than opened directly in GitHub Pages.
