# MCP Gateway

This project is a minimal **gateway-style tool service**: a single FastAPI app that can aggregate multiple local and upstream MCP-backed tools behind one stable API.

## Why a Gateway?

A gateway shape is useful because it makes the tool contract, discovery surface, and error envelope explicit for any external caller.

A gateway helps by centralizing:

- tool registration and discovery
- request routing
- input validation
- consistent error handling
- extension points for auth, rate limits, logging, and policy

This repo is currently focused on the architectural seams that make gateway experimentation useful

The intended model is:

- multiple servers can be connected behind this gateway
- each server can contribute one or more tools
- this repo exposes the unified `/tools` and `/gateway/call` endpoints
- some other client or agent outside this repo can call those endpoints