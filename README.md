# MCP Gateway

This project is a minimal **gateway-style tool service**: a single FastAPI app that exposes a stable tool-facing API with one local sample tool plus optional upstream MCP servers over HTTP.

## Why a Gateway?

A gateway shape is still useful even for a local sample because it makes the tool contract, discovery surface, and error envelope explicit.

A gateway helps by centralizing:

- tool registration and discovery
- request routing
- input validation
- consistent error handling
- extension points for auth, rate limits, logging, and policy

This repo is currently focused on the architectural seams that make gateway experimentation useful