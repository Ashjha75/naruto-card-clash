# Naruto Card Clash — Backend Setup & Build Phases

Base coordinates: `com.ashish:naruto-card-clash`, Spring Boot 4.1.0, Java 25.
Base package: `com.ashish.narutocardclash`.

---

## 1. Confirmed Tech Stack (from your pom.xml)

| Category | Dependency | Purpose |
|---|---|---|
| Web | `spring-boot-starter-webmvc` | REST controllers |
| Web | `spring-boot-starter-websocket` | STOMP over WebSocket for live battles |
| Security | `spring-boot-starter-security` | Auth, route protection |
| Validation | `spring-boot-starter-validation` | `@Valid` on request DTOs |
| Persistence | `spring-boot-starter-data-jpa` | Repository layer, Hibernate |
| Persistence | `spring-boot-starter-flyway` + `flyway-database-postgresql` | Versioned schema migrations |
| Persistence | `postgresql` (runtime) | JDBC driver |
| Redis | `spring-boot-starter-data-redis` | Redis client (Lettuce) |
| Redis | `spring-boot-starter-cache` | `@Cacheable` / `@CacheEvict`, backed by Redis |
| Ops | `spring-boot-starter-actuator` | `/actuator/health`, metrics |
| Auth | `io.jsonwebtoken:jjwt-api` / `jjwt-impl` / `jjwt-jackson` 0.13.0 | Self-issued JWT signing and parsing |
| Dev tooling | `spring-boot-docker-compose` (optional, runtime) | Auto-starts and auto-wires `compose.yaml` |
| Dev tooling | `lombok` (optional) | Boilerplate reduction |
| Test | `webmvc-test`, `security-test`, `data-jpa-test`, `data-redis-test`, `flyway-test`, `websocket-test` | Slice tests for each starter above |

Not present yet, add when you write tests against those slices: `spring-boot-starter-validation-test`, `spring-boot-starter-actuator-test`.

This confirms your auth direction is **stateless JWT**, not server-side
sessions — `spring-boot-starter-session-data-redis` isn't in the pom, `jjwt`
is. Everything in Phase 3 below assumes JWT.

Compiler config: `<release>25</release>` set once at the plugin level (not
per-execution) — Maven applies that to both `default-compile` and
`default-testCompile` automatically, so Lombok's annotation processor runs
correctly on both main and test sources under JDK 25's stricter `-proc`
defaults. No change needed here.

---

## 2. Docker Setup (from your compose.yaml)

```
postgres: postgres:17-alpine   healthcheck: pg_isready        volume: postgres-data
redis:    redis:8-alpine       healthcheck: redis-cli ping    volume: redis-data   --appendonly yes
```

This is solid as-is: named containers, healthchecks with `start_period`,
persistent volumes, AOF enabled on Redis. No fixed host ports — Docker
assigns a random free port, and `spring-boot-docker-compose` reads the
actual bound port at app startup and wires `spring.datasource.*` /
`spring.data.redis.*` for you. That's why you don't (and shouldn't) hand-write
those connection properties in `application.yaml` for local dev.

Not a bug, just a decision to make: you're on `postgres:17-alpine`.
`postgres:18.4-alpine` is the current stable major if you want to move up —
17 is still fully supported, so this is optional, not required.

---

## 3. Fix Required: `application.yaml` indentation

Current file nests `jpa`, `flyway`, `cache` under `spring.docker` instead of
directly under `spring`, and nests `server`, `logging`, `management` under
`spring` instead of at the document root. As written, `spring.jpa.*`,
`spring.flyway.*`, `spring.cache.*`, `server.port`, `logging.level.*`, and
`management.*` are not being read — Spring Boot never looks for properties
at those paths.

Corrected:

```yaml
spring:
  application:
    name: naruto-card-clash-server

  docker:
    compose:
      file: compose.yaml   # optional — auto-detected in the working dir even without this line

  jpa:
    open-in-view: false
    hibernate:
      ddl-auto: validate
    properties:
      hibernate:
        format_sql: true

  flyway:
    enabled: true
    locations: classpath:db/migration

  cache:
    type: redis
    redis:
      time-to-live: 30m
      cache-null-values: false

server:
  port: 8080

logging:
  level:
    org.springframework.security: INFO
    org.hibernate.SQL: INFO

management:
  endpoints:
    web:
      exposure:
        include: health,info
  endpoint:
    health:
      show-details: when-authorized
```

**Verify:** start the app, `GET http://localhost:8080/actuator/health` should
return `200` with `{"status":"UP"}`. That alone won't prove `server.port` is
fixed, since 8080 is also the framework default — to actually confirm it,
temporarily set `server.port: 9090` and check the app comes up on 9090
instead.

---

## 4. Build Phases

Each phase lists the files to add. This is the file-level map, not the
implementation — that comes when we build each module.

### Phase 0 — Done
`pom.xml`, `compose.yaml`, `application.yaml` (needs the fix above),
`NarutoCardClashServerApplication.java`. App boots, containers come up.

### Phase 1 — Foundation
- `application-dev.yaml`, `application-test.yaml`, `application-prod.yaml`
- `common/exception/GlobalExceptionHandler.java`
- `common/dto/ApiResponse.java` — standard `{success, data, error}` envelope
- `common/entity/BaseEntity.java` — `id`, `createdAt`, `updatedAt`, `@Version`
- `db/migration/V1__init.sql` — players, cards, player_cards, games, game_rounds

### Phase 2 — Persistence
- `player/entity/Player.java`, `player/repository/PlayerRepository.java`
- `card/entity/Card.java`, `card/entity/PlayerCard.java` + repositories
- `game/entity/Game.java`, `game/entity/GameRound.java` + repositories
- `db/migration/V2__seed_cards.sql`

### Phase 3 — Auth (JWT)
- `auth/dto/RegisterRequest.java`, `LoginRequest.java`, `AuthResponse.java`
- `auth/service/JwtService.java` — sign/parse via jjwt
- `auth/service/AuthService.java`
- `auth/controller/AuthController.java`
- `auth/filter/JwtAuthFilter.java`
- `config/SecurityConfig.java`

### Phase 4 — Player & Card APIs
- `player/dto/PlayerDTO.java`, `player/service/PlayerService.java`, `player/controller/PlayerController.java`
- `card/dto/CardDTO.java`, `card/service/CardService.java` (`@Cacheable`), `card/controller/CardController.java`

### Phase 5 — WebSocket Skeleton
- `config/WebSocketConfig.java`
- `websocket/interceptor/JwtHandshakeInterceptor.java`
- `websocket/listener/WebSocketEventListener.java` — connect/disconnect

### Phase 6 — Matchmaking
- `matchmaking/service/QuickMatchService.java`, `PrivateRoomService.java`, `MatchmakingScheduler.java`
- `matchmaking/controller/MatchmakingController.java`
- `resources/scripts/join_room.lua`

### Phase 7 — Game Engine
- `game/engine/GameSession.java`, `GameEngine.java`, `TurnTimer.java`
- `game/manager/GameSessionManager.java`
- `game/service/GameService.java`
- `game/dto/MoveRequest.java`

### Phase 8 — Leaderboard
- `leaderboard/service/LeaderboardService.java`
- `leaderboard/controller/LeaderboardController.java`

### Phase 9 — Testing
- Testcontainers base config (Postgres + Redis)
- Concurrency tests: matchmaking double-join, room-join race

### Phase 10 — Frontend
Separate Angular app. Not detailed here.
