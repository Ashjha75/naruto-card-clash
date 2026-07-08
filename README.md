# 🎴 Naruto Card Clash — Real-Time Multiplayer Backend

A production-ready Spring Boot backend for a competitive card-battle game,
designed as a **complete system-design interview portfolio project**.

## Why This Project?

This isn't a toy app — it's a 1v1 real-time game that forces you to solve
the exact problems you'll face in mid/senior backend roles:

- **Stateless REST auth** with JWT + refresh tokens
- **Real-time state sync** over WebSocket/STOMP without losing consistency
- **Distributed matchmaking** on Redis with race-condition protection
- **Game engine** with optimistic locking, turn timers, and reconnection
- **Horizontal scaling** decisions (single-instance vs. Redis-backed state)
- **Concurrency** proofs — not just locks, but intentionally correct under load

## Stack

| Component | Choice | Why |
|-----------|--------|-----|
| Framework | Spring Boot 3 | Industry standard, rich ecosystem |
| Auth | Spring Security + JWT | Stateless, interview-standard |
| Real-time | Spring WebSocket + STOMP | Bi-directional, event-driven |
| DB | PostgreSQL 16 | Relational, ACID, production-grade |
| Cache/Queue/PubSub | Redis 7 | Five distinct usages (see docs) |
| Testing | Testcontainers + JUnit 5 | Real containers, not mocks |
| Containerization | Docker Compose | Dev = prod |

## Architecture Overview

[Simple ASCII diagram from your spec]

## Interview Topics Covered

✅ Spring Security filter chain & JWT design  
✅ WebSocket handshake auth & STOMP protocol  
✅ Redis as queue, cache, Sorted Set, Pub/Sub  
✅ Optimistic vs. pessimistic locking  
✅ Race condition detection & prevention  
✅ State machine design  
✅ N+1 query problems & solutions  
✅ Horizontal scaling trade-offs  
✅ Concurrency-proof testing  
✅ Graceful disconnect/reconnect  

## Quick Start

```bash
git clone https://github.com/yourusername/naruto-card-clash
cd naruto-card-clash
docker-compose up
./mvnw spring-boot:run
```

## Documentation

- [Backend Technical Specification](./docs/BACKEND_SPEC.md) — Deep dive on every module
- [API Reference](./docs/API.md) — All endpoints, request/response shapes
- [Architecture Decisions](./docs/ADR.md) — Why we chose each pattern
- [Concurrency Proofs](./docs/CONCURRENCY.md) — Tests that prove the fixes work

## Project Structure
