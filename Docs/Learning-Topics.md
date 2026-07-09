# Naruto Card Clash — Topics You'll Actually Use

Every row below maps to a real place in this codebase (per the phases in
`BACKEND-SETUP.md`), not a generic "know this for interviews" list. When you
build a phase, come back to the matching section here.

---

## 1. Java — OOP Fundamentals

| Topic | Where it's used |
|---|---|
| Encapsulation | Entity fields kept private, exposed only through DTOs — nothing outside the service layer touches `Player`/`Card` directly |
| Inheritance | `BaseEntity` (`id`, `createdAt`, `updatedAt`, `@Version`) extended by `Player`, `Card`, `Game`, `GameRound` |
| Polymorphism | `Comparator<T>` implementations for leaderboard sorting; any interface with multiple implementations |
| Abstraction | `PlayerRepository extends JpaRepository<Player, UUID>` — you call `findById`, Hibernate does the rest |
| Composition over inheritance | `GameSession` *holds* `List<Card>` rather than extending `Card` — favor "has-a" over "is-a" |
| Interfaces vs abstract classes | Repository interfaces (contract only) vs `BaseEntity` (shared state + behavior) |
| Enums | `GameStatus` (WAITING/IN_PROGRESS/FINISHED), `Stat` (ATTACK/DEFENSE/CHAKRA/SPEED), `Rarity` |
| Access modifiers | Package-private helpers (e.g. `RoomCodeGenerator`) vs public controller methods |

## 2. Java — Language Features

| Topic | Where it's used |
|---|---|
| Generics | `JpaRepository<Player, UUID>`, `ApiResponse<T>`, any generic mapper method |
| Records | Candidate type for DTOs — `LoginRequest`, `MoveRequest`, `ApiResponse` are immutable data carriers, a textbook records use case |
| Sealed interfaces (Java 17+) | Candidate for a `GameEvent` hierarchy (`RoundResultEvent`, `GameOverEvent`, `TimerExpiredEvent`) — sealed gives you exhaustive `switch` with compiler-checked coverage |
| Pattern matching for switch (Java 21+) | Handling WebSocket event types or `GameStatus` transitions without instanceof chains |
| `Optional<T>` | `repository.findById(id)` returns `Optional<Player>` — forces you to handle the not-found case instead of a null check |
| Lambda expressions & functional interfaces | Stream pipelines, `Comparator` chains, `@Scheduled` task bodies |
| Method references | `.map(Card::toDto)` style transformations |
| Text blocks | Multi-line SQL or JSON fixtures in tests |
| `var` (local type inference) | Anywhere the right-hand type is already obvious from context |
| Exception handling | Custom checked/unchecked exceptions (`GameException`, `MatchmakingException`), try-with-resources for anything `Closeable` |
| `equals`/`hashCode` | Needed correctly on any entity you put in a `Set` or use as a `Map` key — Lombok's `@EqualsAndHashCode` handles this, but know *why* it matters |

## 3. Java — Collections & Streams

| Topic | Where it's used |
|---|---|
| `List`, `Map`, `Set` | Hands and won-piles as `List<Card>`; `GameSessionManager` as a `Map<UUID, GameSession>` |
| Stream API | Filtering cards by rarity/village, mapping entity lists to DTO lists |
| `Collectors.groupingBy` | Grouping cards by village or rarity for a filtered catalog view |
| `Comparator.comparing().thenComparing()` | Leaderboard sort: wins descending, then XP as tiebreaker |
| `ConcurrentHashMap` | `GameSessionManager` — see concurrency section, this is a threading topic wearing a collections hat |

## 4. Concurrency & Multithreading

This is the heaviest section — the Game Engine and Matchmaking modules exist specifically to give you real answers here, not textbook ones.

| Topic | Where it's used |
|---|---|
| Thread fundamentals | Understanding that each incoming HTTP/WebSocket request runs on its own thread from the servlet container's pool |
| `ExecutorService` / `ScheduledExecutorService` | Per-turn timers — schedule a forfeit callback, cancel and reschedule on every accepted move |
| Virtual threads (Project Loom, Java 21+, first-class by Java 25) | `spring.threads.virtual.enabled=true` — cheap threads for handling many concurrent WebSocket sessions without pooling tuning |
| `synchronized` / intrinsic locks | `GameEngine.applyMove()` — one lock per session, held for microseconds |
| `ReentrantLock` | Alternative to `synchronized` if you want tryLock-with-timeout semantics instead of indefinite blocking |
| Atomic classes (`AtomicInteger`, `AtomicBoolean`) | Candidate for lock-free counters if you don't go the `stateVersion`-on-the-session route |
| `volatile` | Any flag read by one thread and written by another without a full lock (e.g., a "disconnected" flag) |
| `ConcurrentHashMap` | `GameSessionManager` — active games keyed by game ID, safe for concurrent reads/writes without external locking |
| `CountDownLatch` | Concurrency-proof tests — fire N threads at the exact same instant to try to join one room, assert exactly one wins |
| Optimistic concurrency control | `stateVersion` field on `GameSession`; mirrored by JPA's `@Version` on the `Game` entity — same idea, two layers |
| Pessimistic concurrency (contrast) | `SELECT ... FOR UPDATE` — know when you'd reach for this instead (you don't, here, and should be able to say why) |
| Race conditions catalog | Double room-join, double Quick Match click, stale move after timer expiry — see `BACKEND-SETUP.md` Phase 6–7 |
| Deadlock / livelock / starvation | Theory — and why a single lock per game session with no cross-session locking makes deadlock structurally impossible here |
| Producer-consumer pattern | Redis matchmaking queue: `LPUSH` (producer, on Quick Match click) / `RPOP` (consumer, the scheduler) |
| Thread pool sizing | `@Scheduled` matchmaking job's executor configuration |

## 5. Design Patterns

| Pattern | Where it's used |
|---|---|
| Singleton | Every default Spring `@Service`/`@Component` bean |
| Dependency Injection / Inversion of Control | Constructor injection throughout — know why constructor injection is preferred over field injection (immutability, testability, no reflection hacks) |
| Repository pattern | `JpaRepository` abstractions over Postgres |
| DTO pattern | Entities never cross a controller boundary — always mapped to a DTO first |
| Mapper pattern | Hand-written or MapStruct-generated entity↔DTO conversion |
| Builder pattern | Lombok `@Builder`; `Jwts.builder()` from jjwt |
| Strategy pattern | Candidate for pluggable matchmaking strategies (random pairing vs. ELO-based, if you extend it later) |
| State pattern | `GameStatus` state machine (WAITING → IN_PROGRESS → FINISHED/ABANDONED) |
| Observer pattern | Spring's `ApplicationEventPublisher`, or the WebSocket broadcast-to-subscribers model itself |
| Template method | `RedisTemplate`/`JdbcTemplate`-style callback APIs you'll consume, not write |

## 6. Spring Core

| Topic | Where it's used |
|---|---|
| IoC Container & Dependency Injection | Every `@Service`, `@Repository`, `@Component` in the app |
| Bean scopes | Singleton (default) vs. prototype — know the difference even though you'll mostly use singleton here |
| Bean lifecycle | `@PostConstruct` if you need init logic (e.g., warming the card cache on startup) |
| AOP (Aspect-Oriented Programming) | How `@Transactional` and `@Cacheable` actually work — Spring wraps your bean in a dynamic proxy that intercepts the method call |
| Auto-configuration | Conceptual — how Boot decides to configure a `DataSource` bean because it sees the Postgres driver + `spring-boot-starter-data-jpa` on the classpath |
| Profiles | `application-dev.yaml` / `application-test.yaml` / `application-prod.yaml` |
| `@ConfigurationProperties` vs `@Value` | Binding `jwt.secret`, `jwt.access-token-ttl-minutes` etc. to a typed config class |

## 7. Spring MVC / REST

| Topic | Where it's used |
|---|---|
| `DispatcherServlet` request lifecycle | Conceptual — what happens between a request hitting Tomcat and reaching your controller method |
| `@RestController`, `@RequestMapping`, `@PathVariable`, `@RequestBody` | Every controller: `AuthController`, `PlayerController`, `CardController`, `MatchmakingController`, `LeaderboardController` |
| Global exception handling | `@ControllerAdvice` + `@ExceptionHandler` in `GlobalExceptionHandler` |
| Bean Validation (JSR-380) | `@Valid` on `RegisterRequest`, `LoginRequest`, `MoveRequest` |
| HTTP status code semantics | 400 vs 401 vs 403 vs 409 vs 422 — used correctly in exception mapping, not just 200/500 everywhere |

## 8. Spring Data JPA & Hibernate

| Topic | Where it's used |
|---|---|
| Repository abstraction | `PlayerRepository`, `CardRepository`, `GameRepository`, `GameRoundRepository` |
| Derived query methods | `findByUsername(String username)` style — Spring generates the query from the method name |
| `@Query` / JPQL | Anything a derived method can't express cleanly |
| Pagination | `Pageable` + `Page<T>` on match history and card catalog endpoints |
| Entity relationships | `@OneToMany` (Player → PlayerCard), `@ManyToOne` (PlayerCard → Card) |
| N+1 query problem | The classic bug: loading a player triggers one query per card. Fixed with `@EntityGraph` or `JOIN FETCH` |
| Optimistic locking | `@Version` on `Game` — see the concurrency section, this is the same pattern at the persistence layer |
| Transaction management | `@Transactional` on `AuthService.register()` (create player + grant starter deck must both succeed or both roll back) |
| Lazy vs. eager loading | `FetchType.LAZY` as the default everywhere, and knowing exactly when that causes the N+1 problem above |

## 9. Spring Security

| Topic | Where it's used |
|---|---|
| Filter chain architecture | `SecurityFilterChain` bean in `SecurityConfig`, custom `JwtAuthFilter` slotted into it |
| Authentication vs. Authorization | Login proves *who* you are; `@PreAuthorize` decides *what* you're allowed to do |
| `SecurityContext` / `SecurityContextHolder` | How the authenticated player's identity is available inside a controller without passing it explicitly |
| Stateless JWT auth | Custom `OncePerRequestFilter` that validates the token and populates the security context — no server-side session |
| Password hashing | `BCryptPasswordEncoder` in `AuthService` |
| Method-level security | `@PreAuthorize("hasRole('ADMIN')")` on the admin-only `POST /api/cards` endpoint |

## 10. Spring WebSocket / STOMP

| Topic | Where it's used |
|---|---|
| STOMP protocol frames | `CONNECT` / `SUBSCRIBE` / `SEND` / `DISCONNECT` lifecycle |
| `SimpMessagingTemplate` | Broadcasting `ROUND_RESULT` to `/topic/game/{id}` vs. sending a private error to one player via `/user/queue/game` |
| Handshake interceptors | `JwtHandshakeInterceptor` — auth happens once at connection time, not per message |
| Session lifecycle events | `SessionConnectEvent` / `SessionDisconnectEvent` drive the reconnect grace-period logic |

## 11. Caching

| Topic | Where it's used |
|---|---|
| Cache abstraction | `@Cacheable` on `CardService.getAllCards()`, `@CacheEvict` on card creation |
| Cache-aside pattern | Read path checks Redis first, falls back to Postgres on a miss, populates the cache |
| TTL-based eviction | 24h TTL on the card catalog cache vs. 60s on the leaderboard cache — different data, different staleness tolerance |
| Cache stampede (concept) | What happens if the cache expires under heavy concurrent read load — worth knowing even if you don't build a mitigation for it here |

## 12. PostgreSQL & Database Fundamentals

| Topic | Where it's used |
|---|---|
| ACID properties | The whole reason a relational DB, not Redis, holds the authoritative game/player data |
| Normalization | `player_cards` as a junction table resolving the many-to-many between players and cards |
| Indexes (B-tree) | On every foreign key you query by — `player_id` on `player_cards`, `game_id` on `game_rounds` |
| Transactions & isolation levels | Default Read Committed in Postgres — know what it does and doesn't protect against |
| Row-level locking | `SELECT ... FOR UPDATE` as the pessimistic alternative to the `@Version` optimistic approach actually used here |
| Foreign keys & referential integrity | Every `_id` column in the schema |
| UUID vs. auto-increment PKs | This schema uses UUIDs — know the trade-off (no enumeration/guessing, but larger index size and no natural ordering) |
| Connection pooling | HikariCP, Spring Boot's default pool — `maximum-pool-size`, `minimum-idle` |
| `EXPLAIN ANALYZE` | How you'd actually verify an index is being used instead of assuming it |
| Flyway migrations | Why versioned SQL files beat `ddl-auto: update` for anything beyond a toy project |

## 13. Redis

| Topic | Where it's used |
|---|---|
| Core data structures | List (matchmaking queue), Hash (private rooms), Sorted Set (leaderboard), String (card cache JSON, rate limiting) |
| Atomicity of single commands | Why `RPOP` alone is enough to prevent double-pairing from the matchmaking queue |
| Lua scripting | The room-join script — check-and-set has to be atomic across two operations, which requires a script, not two round trips |
| `SETNX` | Idempotency lock preventing a double Quick Match click |
| TTL / expiry | 5-minute auto-expiring private rooms |
| Sorted Sets for leaderboards | `ZADD`, `ZREVRANGE`, `ZREVRANK` — O(log N) updates and range reads |
| Pub/Sub (conceptual) | How you'd fan out WebSocket broadcasts across multiple app instances if you scaled horizontally |

## 14. System Design Concepts

| Topic | Where it's used |
|---|---|
| CAP theorem / consistency trade-offs | Strong consistency for game state (can't lose a card), eventual consistency for the leaderboard (a few seconds of staleness is fine) |
| Idempotency | Matchmaking's `SETNX` guard, `UNIQUE(game_id, round_number)` preventing duplicate round inserts on retry |
| Horizontal scaling & statelessness | Why `GameSessionManager` as a plain in-memory map only works single-instance, and what moving it to Redis + Pub/Sub would take |
| Rate limiting algorithms | Fixed-window counter (`INCR`+`EXPIRE`) as implemented, and its known burst-at-the-boundary flaw vs. sliding window/token bucket |
| Distributed locking | `SETNX` as a lightweight distributed lock |

## 15. Testing

| Topic | Where it's used |
|---|---|
| JUnit 5 | Lifecycle annotations (`@BeforeEach`, `@Test`), parameterized tests for stat-comparison logic |
| Mockito | Mocking repositories in service-layer unit tests |
| Testcontainers | Real Postgres + Redis containers in integration tests, not H2 or mocks |
| `MockMvc` | REST endpoint tests via `spring-boot-starter-webmvc-test` |
| Concurrency testing | `ExecutorService` + `CountDownLatch` to fire concurrent requests and assert exactly one wins — the single most interview-differentiating test in this project |