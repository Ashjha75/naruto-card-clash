# Naruto Card Clash — Project Overview

## What This Is

A real-time 1v1 card-battle game (Top Trumps-style mechanics). Two players
each hold a hand of Naruto character cards; each round the active player
picks a card and a stat (Attack / Defense / Chakra / Speed); higher stat
wins the round and takes both cards. Best pile after 5 rounds wins. Matches
happen live over WebSocket, with a queue-based quick match and a
private-room-with-code option.

This doc is the one-page picture: what's in the stack and how a player
moves through the app. Backend implementation detail lives in
`BACKEND-SETUP.md`.

## Tech Stack

### Frontend (planned, not started yet)

| Layer | Choice | Role |
|---|---|---|
| Framework | Angular | SPA client |
| Comms | REST + WebSocket (STOMP) | Talks to the Spring Boot backend |

### Backend

| Layer | Choice | Role |
|---|---|---|
| Language | Java 25 (LTS) | |
| Framework | Spring Boot 4.1 | REST API, WebSocket, DI, auto-config |
| Auth | Spring Security + JWT (jjwt) | Stateless auth |
| Real-time | Spring WebSocket (STOMP) | Live battle state |
| Database | PostgreSQL | Players, cards, match history |
| Migrations | Flyway | Versioned schema changes |
| Cache / Queue | Redis | Matchmaking queue, card cache, leaderboard |

### Infrastructure

| Tool | Role |
|---|---|
| Docker Compose | Runs Postgres + Redis locally |
| `spring-boot-docker-compose` | Auto-starts those containers and auto-wires the app to them — no manual connection config in dev |

## High-Level User Journey

```
Landing Page
   |
   v
Sign Up / Log In  ---->  starter deck of 10 cards granted
   |
   v
Home Screen (profile, card collection, stats)
   |
   +--> Quick Match  ---> matchmaking queue ---> opponent found
   |
   +--> Create / Join Private Room ---> room code shared ---> opponent joins
   |
   v
Battle Screen (5 rounds, live over WebSocket)
   |
   v
Game Over Screen (result, stats updated)
   |
   v
Home Screen / Leaderboard / Profile
```

## System Shape

```
Angular client
   |  REST          (auth, profile, cards)
   |  WebSocket/STOMP (live battle)
   v
Spring Boot backend
   |                     |
   v                     v
PostgreSQL            Redis
(durable data:       (matchmaking queue,
 players, cards,       card cache,
 match history)         leaderboard)
```
