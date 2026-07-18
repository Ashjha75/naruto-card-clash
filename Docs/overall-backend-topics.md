# Backend Revision Notes — Spring Boot

### A senior dev's checklist: read this before writing any layer

This is not a tutorial. It is a structured reminder of how things actually
work, in the order they happen during a real request, plus the supporting
systems around that lifecycle. Every section answers two questions:
what is actually happening here, and what do you need to remember when
you write code for this layer.

---

## HOW A REQUEST FLOWS — the mental model

Before anything specific, burn this sequence into your head.
Every backend request, without exception, passes through this:

```
Client (browser / mobile / Postman)
   |
   | HTTP/HTTPS
   v
[1] Network / Load Balancer / Reverse Proxy  (Nginx, etc — not your code)
   |
   v
[2] Servlet Container  (Tomcat — embedded in Spring Boot)
   |
   v
[3] Filter Chain  (executes before Spring even sees the request)
   |
   v
[4] DispatcherServlet  (Spring's front controller — one instance, all requests)
   |
   v
[5] Interceptor (pre-handle)
   |
   v
[6] Argument Resolvers  (turn HTTP params/body into Java method args)
   |
   v
[7] Controller Method  (your @RestController)
   |
   v
[8] Service Layer  (@Service — business logic, transaction boundary)
   |
   v
[9] Repository / Cache / Queue / External Call
   |
   v
[8] Service returns result
   |
   v
[7] Controller builds response
   |
   v
[5] Interceptor (post-handle / after-completion)
   |
   v
[10] Message Converters  (Java object → JSON via Jackson)
   |
   v
[3] Filter Chain (response direction)
   |
   v
Client receives response
```

Each numbered section below covers one layer of this stack.

---

## 1. NETWORK LAYER — not your code, but you need to understand it

**What happens:** HTTPS termination, TLS handshake, load balancing, request
routing. In production this is Nginx or a cloud load balancer sitting in
front of your Spring Boot app.

**What you need to know:**

- Your app receives plain HTTP from the reverse proxy, not HTTPS — TLS is
  terminated upstream. Don't add TLS in Spring Boot unless you have a
  specific reason.
- `X-Forwarded-For`, `X-Forwarded-Proto`, `X-Real-IP` headers — the proxy
  adds these so your app knows the real client IP and original protocol.
  Spring Boot's `ForwardedHeaderFilter` (or `server.forward-headers-strategy:
native` in `application.yaml`) processes them so `request.getRemoteAddr()`
  gives you the real IP, not the proxy's.
- **Why it matters for you:** rate limiting, CORS, logging — all of these
  need the real client IP, not `127.0.0.1`.

---

## 2. SERVLET CONTAINER (Tomcat)

**What happens:** Tomcat receives the raw TCP connection, parses the HTTP
bytes into a `HttpServletRequest` object, manages a thread pool (one thread
per request — the traditional model), and hands the request to the filter
chain.

**What you need to know:**

- Spring Boot embeds Tomcat — you don't configure it separately, it's a
  library inside your fat jar.
- **Thread pool:** by default, Tomcat runs with a fixed pool of 200 threads.
  Each blocking request (one waiting on a DB call) ties up one thread. This
  is fine at low scale; understand it exists so you can explain the
  bottleneck if asked.
- **Java 25 / Virtual threads:** `spring.threads.virtual.enabled: true` in
  `application.yaml` makes Tomcat use virtual threads instead of platform
  threads — millions of cheap threads instead of 200 expensive ones. You get
  this almost for free on Java 21+. Enables higher concurrency under
  I/O-heavy workloads without async/reactive code.
- **`HttpServletRequest` / `HttpServletResponse`:** the raw objects
  everything else wraps. Understanding them directly helps when you're
  debugging filters or writing things that don't fit neatly into Spring's
  abstractions.

---

## 3. FILTER CHAIN

**What happens:** A series of `javax.servlet.Filter` (now
`jakarta.servlet.Filter`) implementations that execute before and after
every request. They wrap the entire request lifecycle — they run before
Spring's DispatcherServlet, and they run on the way back out too.

**What you need to know:**

- Filters are Servlet-level — they know nothing about Spring controllers,
  `@RequestMapping`, or beans. They work with raw `HttpServletRequest` /
  `HttpServletResponse`.
- **Order matters.** Filters form a chain; the order they execute is
  controlled by `@Order` or by registering them as `FilterRegistrationBean`
  with an explicit order number.
- **Spring Security is implemented as a single filter** (`DelegatingFilterProxy`)
  that internally runs its own chain of security filters. This is why
  Security runs so early — it's at the Servlet filter level, not inside
  Spring MVC.
- **Your `JwtAuthFilter` is a filter.** It extends `OncePerRequestFilter`
  (guarantees it runs exactly once per request, not once per dispatch).
  It reads the `Authorization` header, validates the JWT, and populates
  `SecurityContextHolder` — all before the request reaches a controller.
- **Common built-in filters you'll encounter:** `CorsFilter`, `CharacterEncodingFilter`,
  `ForwardedHeaderFilter`, Spring Security's `SecurityContextPersistenceFilter`.

```
Built-in filters run
   → JwtAuthFilter (yours — reads JWT, populates SecurityContext)
   → CorsFilter (handles preflight and headers)
   → Request reaches DispatcherServlet
```

**Checklist before writing a filter:**

- Does this need to know about Spring beans? → Yes: extend `OncePerRequestFilter`
  and annotate `@Component`, Spring injects beans normally.
- Does this need to run for every URL including static resources?
  → Filter. If only for controller routes → Interceptor (see §5).
- Is execution order important relative to Security? → Yes, always check
  where in the chain yours slots in relative to `SecurityFilterChain`.

---

## 4. DISPATCHER SERVLET

**What happens:** Spring MVC's single front controller. Every request that
makes it past the filter chain arrives here. It looks up which `@Controller`
method maps to this URL + HTTP method, triggers argument resolution,
calls the method, and sends the result through message converters.

**What you need to know:**

- There is **one** `DispatcherServlet` instance. It's not a bottleneck
  because it's stateless — it just routes, it holds nothing.
- It delegates to `HandlerMapping` to find the controller, `HandlerAdapter`
  to actually call it, and `ViewResolver` (not relevant for REST — you're
  using `@ResponseBody`/`@RestController` which bypasses view resolution).
- **`@RestController` = `@Controller` + `@ResponseBody`** on every method.
  `@ResponseBody` is the instruction that tells the DispatcherServlet "don't
  look for a view — convert the return value directly to the response body
  using a `MessageConverter`."
- You will almost never touch `DispatcherServlet` directly. Know it exists,
  know it's the entry point to Spring MVC, know that if a request never
  reaches your controller, a filter or interceptor rejected it.

---

## 5. INTERCEPTORS

**What happens:** `HandlerInterceptor` runs inside Spring MVC, after the
DispatcherServlet has found the controller but before (and after) it calls
the method. Three hooks: `preHandle`, `postHandle`, `afterCompletion`.

**What you need to know:**

- Unlike filters, interceptors know about the handler (which controller
  method is being called) — you can make decisions based on that.
- `preHandle` returns `boolean` — return `false` to abort the request here.
- `postHandle` runs after the controller but before the response is written
  — you can add headers, modify the `ModelAndView` (not relevant for REST).
- `afterCompletion` runs after the response is fully written, even if an
  exception was thrown — use it for cleanup, metrics, logging.
- **Typical uses:** logging request duration, adding correlation IDs to MDC,
  rate-limiting checks that need to know which endpoint is being hit.
- **Not for auth.** Auth belongs in filters (Security runs at filter level)
  because filters execute before the DispatcherServlet — if auth were in an
  interceptor, unauthenticated requests would still reach the DispatcherServlet
  before being rejected, which is too late.

---

## 6. ARGUMENT RESOLUTION

**What happens:** Before Spring calls your controller method, it needs to
turn the raw HTTP request into Java method arguments. Each `@RequestBody`,
`@PathVariable`, `@RequestParam`, `@RequestHeader` annotation is handled by
a dedicated `HandlerMethodArgumentResolver`.

**What you need to know:**

- `@RequestBody` triggers `HttpMessageConverter` to parse the JSON body into
  your DTO — Jackson does this by default.
- `@Valid` or `@Validated` on a `@RequestBody` parameter triggers Bean
  Validation at this layer, before your method body runs.
- `@PathVariable` extracts from the URL, `@RequestParam` from the query
  string, `@RequestHeader` from headers.
- `@AuthenticationPrincipal` is a special resolver that extracts the
  currently authenticated user from `SecurityContextHolder` and injects it
  directly as a method parameter — cleaner than calling
  `SecurityContextHolder.getContext().getAuthentication()` yourself inside
  every method.

---

## 7. CONTROLLER LAYER

**What is its job:** Entry point into your application logic. Receives
validated, deserialized input. Calls the service. Returns a DTO wrapped in
`ResponseEntity` or `ApiResponse`. Nothing else.

**What the controller must NEVER do:**

- Business logic — that belongs in the service.
- Database access — that belongs in the repository.
- Entity objects must never leave the controller in a response — always map
  to a DTO first.
- `@Transactional` — never on a controller method. The transaction boundary
  belongs in the service.

**What you need to know:**

- `ResponseEntity<T>` lets you control the HTTP status code, headers, and
  body explicitly. Use it when the status code varies (201 vs 200).
- `@ResponseStatus` is a shorthand when the status is always the same.
- `@RequestMapping` at class level + specific mapping at method level — the
  class-level mapping is a prefix, every method under it inherits it.
- Controller methods are stateless — no instance variables. The same
  instance handles thousands of requests concurrently; any state stored
  in a field creates a data race.
- Validation errors (`BindingResult`, `MethodArgumentNotValidException`) are
  thrown before your method runs when `@Valid` fails — catch them in
  `GlobalExceptionHandler`, not in the controller method itself.

---

## 8. SERVICE LAYER

**What is its job:** All business logic. Owns the transaction boundary.
Coordinates between repositories, cache, external calls, and domain logic.

**What you need to know:**

### @Transactional

- Put it on **service methods**, not controllers, not repositories.
- Default propagation: `REQUIRED` — joins an existing transaction if one
  exists, creates a new one if not.
- Default rollback: only on `RuntimeException` and `Error` — checked
  exceptions do NOT trigger rollback by default. Use
  `@Transactional(rollbackFor = Exception.class)` if you need that.
- `@Transactional` works via Spring AOP proxy — it only intercepts calls
  from outside the class. A `public` method in a service calling another
  `public` method in the same class bypasses the proxy and skips the
  transaction. This is the single most common `@Transactional` bug.
- `readOnly = true` on read-only methods — tells Hibernate to skip dirty
  checking, tells the DB driver it can use a read replica if configured.
  Minor performance gain, good habit.

### AOP (how @Transactional and @Cacheable actually work)

- Spring wraps your `@Service` bean in a dynamic proxy at startup.
- When you call a `@Transactional` method, you're actually calling the
  proxy's method, which begins a transaction, then delegates to your real
  method, then commits or rolls back.
- Same mechanism for `@Cacheable` — the proxy intercepts the call, checks
  the cache, either returns from cache or calls your real method and stores
  the result.
- **Implication:** if you `@Autowired` a service and call it from outside
  the class, you get the proxy (correct behavior). If you call it from
  within the same class, you bypass the proxy (wrong behavior — no
  transaction, no cache).

---

## 9. SECURITY — Authentication & Authorization

Two different concepts. Get them separate in your head permanently:

- **Authentication:** who are you? (prove identity)
- **Authorization:** what are you allowed to do? (check permission)

### Spring Security Filter Chain

```
Every request
   → SecurityContextPersistenceFilter  (loads/saves SecurityContext)
   → JwtAuthFilter (yours)             (validates JWT, sets Authentication)
   → ExceptionTranslationFilter        (catches auth/authz exceptions, returns 401/403)
   → FilterSecurityInterceptor         (enforces URL-level rules)
```

### Authentication — how JWT works in your app

1. Client sends `Authorization: Bearer <token>` header.
2. `JwtAuthFilter` intercepts every request, extracts the token.
3. `JwtService` validates: signature correct? not expired? not blacklisted?
4. If valid: creates `UsernamePasswordAuthenticationToken` with player ID
   and roles, sets it in `SecurityContextHolder`.
5. Downstream code (controller, service) reads identity from
   `SecurityContextHolder.getContext().getAuthentication()`.
6. If invalid: `SecurityContextHolder` stays empty → `ExceptionTranslationFilter`
   catches the missing authentication → returns `401`.

**What you need to know about JWT itself:**

- Three parts: `header.payload.signature`, each Base64-encoded,
  separated by dots.
- Header: algorithm (`HS256`, `RS256`). Payload: claims (`sub`, `exp`,
  `iat`, `jti`, `roles`). Signature: HMAC of header+payload with your secret.
- **JWT is signed, not encrypted.** The payload is readable by anyone who
  has the token — never put passwords, full PII, or secrets in a JWT payload.
- `sub` (subject): the player's UUID. `exp`: expiry timestamp. `jti`:
  unique token ID, used for blacklisting.
- Access token: short-lived (15 min). Refresh token: longer-lived (7 days),
  opaque string stored hashed server-side, used to get a new access token.
- **Why short-lived access tokens?** A stolen token is valid only until it
  expires. You can't revoke a JWT mid-flight without a blacklist lookup —
  the blacklist is the compromise between "pure stateless" and "can revoke
  immediately."

### Authorization

- **URL-level:** `SecurityConfig` — `http.authorizeHttpRequests()` — rules
  applied before the request reaches a controller. `permitAll()` for public
  endpoints, `authenticated()` for everything else.
- **Method-level:** `@PreAuthorize("hasRole('ADMIN')")` on controller/service
  methods — evaluated by Spring Security AOP after the controller is found,
  before the method runs. Requires `@EnableMethodSecurity` in `SecurityConfig`.
- **Domain-level:** not Spring Security's job — this is your code in the
  service layer: "does this player actually own this card?" can't be answered
  by a URL rule or a role annotation; it requires a database lookup.
  `MoveValidator` in the game engine is domain-level authorization.

### CORS (Cross-Origin Resource Sharing)

**What it is:** a browser security mechanism. When your Angular app on
`localhost:4200` calls your API on `localhost:8080`, the browser sees two
different origins and blocks the request unless the server explicitly allows
it.

**What happens:**

1. Browser sends a preflight `OPTIONS` request first.
2. Your server responds with `Access-Control-Allow-Origin`,
   `Access-Control-Allow-Methods`, `Access-Control-Allow-Headers` headers.
3. Browser decides if the actual request is allowed.

**In Spring Boot:** configure it globally in `SecurityConfig` or a
`CorsConfig` bean — not per-controller. A `@CrossOrigin` annotation on every
controller is messy and error-prone.

```java
// in SecurityConfig
http.cors(cors -> cors.configurationSource(corsConfigurationSource()));

@Bean
CorsConfigurationSource corsConfigurationSource() {
    var config = new CorsConfiguration();
    config.setAllowedOrigins(List.of("http://localhost:4200"));
    config.setAllowedMethods(List.of("GET","POST","PUT","DELETE","OPTIONS"));
    config.setAllowedHeaders(List.of("*"));
    config.setAllowCredentials(true);
    var source = new UrlBasedCorsConfigurationSource();
    source.registerCorsConfiguration("/**", config);
    return source;
}
```

**Never use `allowedOrigins("*")` with `allowCredentials(true)`** — the
browser blocks it and Spring throws an error. Either enumerate origins or
disable credentials.

### CSRF (Cross-Site Request Forgery)

**What it is:** an attack where a malicious site tricks a logged-in user's
browser into making a request to your API using the user's session cookie.

**For REST APIs using JWT (stateless, no cookies):** CSRF is not a real
threat — there's no cookie for the browser to automatically send. Disable
it: `http.csrf(csrf -> csrf.disable())`. If you were using session cookies
instead of JWT, you'd need CSRF protection.

---

## 10. VALIDATION

Two different layers — both are needed, they protect different things:

### Layer 1: Bean Validation (Jakarta Validation, JSR-380)

Runs at argument resolution time, before the controller method body.

```java
// on the DTO
public record RegisterRequest(
    @NotBlank @Size(min=3, max=30) String username,
    @Email @NotBlank String email,
    @NotBlank @Size(min=8) String password
) {}

// on the controller
@PostMapping("/register")
public ResponseEntity<?> register(@Valid @RequestBody RegisterRequest req) { ... }
```

Failure throws `MethodArgumentNotValidException` → caught in
`GlobalExceptionHandler` → returns `400 Bad Request` with field errors.

**Annotations you'll use:** `@NotNull`, `@NotBlank`, `@NotEmpty`, `@Size`,
`@Min`, `@Max`, `@Email`, `@Pattern`, `@Positive`.

**Custom validator:** implement `ConstraintValidator<YourAnnotation, YourType>`
when built-ins aren't enough (e.g., "both passwords must match").

### Layer 2: Domain Validation (your code, in the service/MoveValidator)

Business rules that can't be expressed as a DTO annotation:

- Does this player actually own this card?
- Is it this player's turn?
- Is the room code still valid?
- Is this username already taken?

Domain validation failures throw your custom exceptions (`GameException`,
`MatchmakingException`) → caught in `GlobalExceptionHandler` → return the
appropriate 4xx status.

**Rule: Bean Validation catches "is this a valid request shape?" — Domain
validation catches "is this request valid given the current state of the
world?"**

---

## 11. ERROR HANDLING

### @ControllerAdvice / GlobalExceptionHandler

One class handles all exceptions across all controllers. The pattern:

```java
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(MethodArgumentNotValidException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public ApiResponse<?> handleValidationError(MethodArgumentNotValidException ex) {
        // extract field errors, return structured error response
    }

    @ExceptionHandler(ResourceNotFoundException.class)
    @ResponseStatus(HttpStatus.NOT_FOUND)
    public ApiResponse<?> handleNotFound(ResourceNotFoundException ex) { ... }

    @ExceptionHandler(UnauthorizedActionException.class)
    @ResponseStatus(HttpStatus.FORBIDDEN)
    public ApiResponse<?> handleForbidden(UnauthorizedActionException ex) { ... }

    @ExceptionHandler(Exception.class)  // catch-all — last resort
    @ResponseStatus(HttpStatus.INTERNAL_SERVER_ERROR)
    public ApiResponse<?> handleGeneric(Exception ex) { ... }
}
```

**What you need to know:**

- Never expose stack traces to the client. Log them server-side at `ERROR`
  level, return a clean `{ code, message }` to the client.
- Return different HTTP status codes for different error types — 400, 401,
  403, 404, 409 each mean something specific to the client. Don't collapse
  everything to 400 or 500.
- Order your `@ExceptionHandler` methods from most specific to least specific.
  Spring picks the most specific handler that matches.
- The catch-all `Exception.class` handler is a safety net — if it fires in
  production, it means you haven't handled a type you should have. Log it
  loudly.

---

## 12. CACHING

### How @Cacheable works

```java
@Cacheable(value = "cards", key = "'all'")
public List<CardDTO> getAllCards() {
    return cardRepository.findAll().stream().map(mapper::toDto).toList();
}
```

1. Spring's caching proxy intercepts the method call.
2. Checks Redis for key `cards::all`.
3. **Hit:** returns cached value, the real method never runs.
4. **Miss:** calls the real method, stores the result in Redis with the
   configured TTL, returns the result.

`@CacheEvict(value = "cards", allEntries = true)` — when a card is created
or updated, this annotation tells Spring to delete the cached entry so the
next read gets fresh data.

**What you need to know:**

- `@Cacheable` only works on public methods called from outside the class
  (same AOP proxy rule as `@Transactional`).
- `key` must be a SpEL expression — `"'all'"` is a literal string, while
  `"#id"` references a method parameter named `id`.
- If your method can return `null`, set `cache-null-values: false` in config
  — otherwise null gets cached and you serve a null response to every
  subsequent request until TTL expires.
- TTL in `application.yaml` (`spring.cache.redis.time-to-live`) is the
  global default; override per cache name in `CacheConfig`.
- **Cache-aside vs. read-through:** `@Cacheable` is cache-aside — the
  application checks the cache, falls back to the DB. The cache is a
  distinct layer, not transparent. Know the term.

---

## 13. DATABASE LAYER

### JPA / Hibernate

- JPA is the specification (interface). Hibernate is the implementation.
  Spring Data JPA wraps both.
- `@Entity` marks a class as a DB table. `@Column` controls column mapping.
  `@ManyToOne`, `@OneToMany`, `@ManyToMany` define relationships.
- `FetchType.LAZY` (default for collections): related entities are loaded
  only when you access them. `FetchType.EAGER`: loaded immediately in the
  same query.

### The N+1 Query Problem — the most common JPA bug

```
// You load 20 players in one query
List<Player> players = playerRepository.findAll();

// Then for each player you access their cards
// → Hibernate fires ONE query per player to load cards
// → 1 query for players + 20 queries for cards = 21 queries
players.forEach(p -> p.getCards().size());
```

Fix: `JOIN FETCH` in a JPQL query, or `@EntityGraph` annotation — loads
everything in one query with a JOIN.

### Transaction isolation levels

- **Read Uncommitted:** can read data that's been modified but not committed
  (dirty reads). Never use.
- **Read Committed (Postgres default):** only reads committed data. Still
  has non-repeatable reads (same row, two reads in one transaction, different
  values). Fine for most use cases.
- **Repeatable Read:** same row reads are consistent within a transaction.
- **Serializable:** full isolation, highest consistency, highest contention.
  Use only when you absolutely need it.

### Connection Pool (HikariCP)

Tomcat has a thread pool; Postgres has a `max_connections` limit. HikariCP
sits between them, reusing a fixed number of already-open connections.
If all connections are busy, new requests wait. Pool size × query time =
throughput ceiling you need to understand when debugging slow endpoints.

---

## 14. REDIS — the five distinct roles

Redis is a data structure server, not just a cache. In this project it
plays five different roles — they're listed here as distinct so you don't
mentally collapse them into "Redis = cache."

### 1. Cache (Cache-Aside)

String key → JSON value, TTL-bounded. `@Cacheable` / `@CacheEvict`.
Used for: card catalog.

### 2. Queue (Producer-Consumer)

Redis List. `LPUSH` adds to the front, `RPOP` removes from the back.
Single-threaded Redis guarantees `RPOP` is atomic — only one consumer
gets each element.
Used for: matchmaking queue.

### 3. Distributed Lock (SETNX)

`SET key value NX EX 10` — set only if not exists, with 10s expiry.
Returns success or failure atomically. Used to prevent double-click
idempotency bugs.
Used for: matchmaking entry guard.

### 4. Ephemeral State with TTL

Hash or String with a TTL. The key auto-deletes when time expires —
no cleanup code needed.
Used for: private room codes (5 min TTL).

### 5. Sorted Set (Leaderboard)

`ZADD key score member` — O(log N). `ZREVRANGE key 0 99 WITHSCORES`
— top 100 in O(log N + 100). `ZREVRANK key member` — my rank in
O(log N). The canonical leaderboard data structure.
Used for: leaderboard.

### Lua scripts — atomicity across multiple commands

Two separate Redis commands are not atomic together. Between `GET` and `SET`
another client can slip in. A Lua script runs on the Redis server as a
single atomic unit — no other command can execute between the script's
lines.
Used for: private room join (check if full, then claim — must be atomic).

---

## 15. WEBSOCKET & STOMP

### What WebSocket is

A persistent, full-duplex TCP connection. Unlike HTTP (client asks, server
answers, connection closes), WebSocket stays open — the server can push data
to the client at any time. Established via an HTTP Upgrade handshake.

### What STOMP is

A simple text-based messaging protocol layered over WebSocket. Like HTTP
for WebSocket — adds message framing (`CONNECT`, `SUBSCRIBE`, `SEND`,
`DISCONNECT` frames), destinations (like URLs), and a message header format.
Spring's WebSocket support uses STOMP.

### Key concepts

- **`/topic/...`** — broadcast destinations. All subscribers receive the
  message. Used for: game events both players see (round result, timer).
- **`/user/queue/...`** — per-user private destinations. `SimpMessagingTemplate.
convertAndSendToUser()` routes to one specific connected client. Used
  for: matchmaking result, personal errors.
- **`/app/...`** — messages from the client to a `@MessageMapping` method
  on your controller.
- **`SimpMessagingTemplate`** — the Spring bean you inject into services to
  send messages to subscribed clients from server-initiated code.

### Authentication on WebSocket

JWT validated **once** at the STOMP `CONNECT` frame (in
`JwtHandshakeInterceptor`), not on every message. The player ID is stored
in the STOMP session attributes for the duration of the connection.
Per-message auth would be expensive and unnecessary — if they connected
authenticated, they stay authenticated until disconnect.

### Session lifecycle events

- `SessionConnectEvent` — client connected. Add to `GameSessionManager`'s
  tracking of connected players.
- `SessionDisconnectEvent` — client dropped. Start the grace-period timer.
  Don't immediately forfeit — network blips are common.

---

## 16. CONCURRENCY — what actually happens when two requests touch the same data

### The problem

Tomcat runs many threads concurrently. If two threads both read a value,
modify it, and write it back, the second write can overwrite the first's
work — a lost update. The game engine is the critical example: two players'
moves processed simultaneously could corrupt the game state.

### Optimistic Locking (@Version)

No actual lock is held. Everyone reads freely. When writing, Hibernate
appends `WHERE version = ?` to the UPDATE. If another transaction already
incremented the version, your update hits 0 rows → `OptimisticLockException`
→ you retry or fail. Best for low-contention scenarios. This is what your
`BaseEntity.version` field does.

### Pessimistic Locking (SELECT FOR UPDATE)

An actual database row lock. No other transaction can read-for-update or
write the row until you release it. Best for high-contention, short
transactions. You're not using this — but know when you would: claiming a
limited resource where retrying an optimistic failure would be an infinite
loop.

### synchronized in Java

Intrinsic lock on an object. Only one thread at a time executes the
synchronized block. Used in `GameEngine.applyMove()` — a per-session lock
held for microseconds (just the move validation and state mutation), never
while waiting for I/O. Never hold a synchronized block while making a
network call or DB call.

### ConcurrentHashMap

Thread-safe `HashMap` implementation. `get`/`put` on different keys don't
block each other — fine-grained locking per bucket. Used for
`GameSessionManager` — multiple games running concurrently, each in its own
session, no cross-session locking needed.

### AtomicBoolean / AtomicInteger

Lock-free thread-safe primitives using CPU-level CAS (compare-and-swap).
`atomicBoolean.compareAndSet(false, true)` — sets to true only if it was
false, atomically. No synchronized block needed. Use for simple flags and
counters where you'd otherwise add a full lock.

### Race conditions you'll specifically encounter

- **Double Quick Match click:** player sends two quick-match requests before
  the first one processes → duplicate queue entries. Fix: `SETNX`
  idempotency lock.
- **Two players join the same room simultaneously:** both pass the "is room
  full?" check before either one sets "room is now full." Fix: Lua script.
- **Stale move after timer expiry:** timer fires, auto-forfeits the round,
  increments `stateVersion`; then the player's actual move arrives with the
  old `stateVersion`. Fix: reject the stale `stateVersion`, move is a no-op.
- **Duplicate round insert on retry:** network error, client retries, server
  processes the round twice. Fix: `UNIQUE(game_id, round_number)` DB
  constraint.

---

## 17. LOGGING

### Why structured logging matters

`System.out.println` or even unstructured log lines are unqueryable. In
production you want to search logs by `gameId`, or find all errors for a
specific player — that requires a structured, parseable format (JSON).

### SLF4J + Logback (Spring Boot's default)

```java
private static final Logger log = LoggerFactory.getLogger(GameEngine.class);

log.info("Move applied: gameId={} playerId={} stat={}", gameId, playerId, stat);
log.error("Unexpected error in game engine: gameId={}", gameId, ex);
```

**What you need to know:**

- Use parameterized logging (`{}` placeholders) — not string concatenation.
  Concatenation builds the string even if that log level is disabled;
  placeholders don't.
- Set log levels in `application.yaml`, not in code — `DEBUG` in dev,
  `INFO` in prod, targeted to packages.
- **MDC (Mapped Diagnostic Context):** a per-thread key-value store that
  gets attached to every log line automatically. Set `gameId` in MDC at
  the start of a game request — every subsequent log line in that thread
  includes it without you having to pass it around.
- `logback-spring.xml` in `src/main/resources` — the structured JSON log
  config. Outputs one JSON object per line, each with timestamp, level,
  logger, message, and any MDC fields.

---

## 18. CONFIGURATION & PROFILES

### application.yaml hierarchy

Spring loads configuration in order, later entries override earlier ones:

```
application.yaml               (base, always loaded)
application-{profile}.yaml     (profile-specific, loaded when active)
Environment variables           (override everything)
```

`SPRING_PROFILES_ACTIVE=prod` activates `application-prod.yaml`. In dev,
`application-dev.yaml` has relaxed settings. In tests,
`application-test.yaml` points to Testcontainers.

### @ConfigurationProperties vs @Value

```java
// @Value — simple, fine for one or two properties
@Value("${jwt.secret}") private String secret;

// @ConfigurationProperties — better for a group of related properties
@ConfigurationProperties(prefix = "jwt")
public record JwtProperties(String secret, long expirationMs) {}
```

`@ConfigurationProperties` is type-safe, IDE-autocomplete works, and it's
easier to test — inject the record directly. Prefer it for anything beyond
a single property.

### Secrets

Never in `application.yaml` committed to git. Use environment variables —
`${JWT_SECRET}` in yaml, real value in `.env` (gitignored) or injected by
the deployment platform. `spring-boot-docker-compose` reads from Docker
Compose environment fields at dev time.

---

## 19. TESTING LAYERS

| Test type           | What it tests                       | Spring Boot annotation | DB / Redis            |
| ------------------- | ----------------------------------- | ---------------------- | --------------------- |
| Unit                | One class in isolation              | none                   | Mocked (Mockito)      |
| Repository slice    | JPA queries, Flyway migrations      | `@DataJpaTest`         | Real (Testcontainers) |
| Service integration | Service + real DB + real Redis      | `@SpringBootTest`      | Real (Testcontainers) |
| Controller slice    | HTTP layer, security, serialization | `@WebMvcTest`          | Mocked service layer  |
| WebSocket           | Full STOMP connect/send/receive     | `@SpringBootTest`      | Real                  |
| Concurrency proof   | Race conditions under parallel load | `@SpringBootTest`      | Real                  |

### Key concepts

- **Mockito:** `@Mock` creates a mock, `@InjectMocks` injects mocks into
  the class under test. `when(repo.findById(id)).thenReturn(Optional.of(player))`
  stubs a call. `verify(repo, times(1)).save(any())` asserts a call happened.
- **`@DataJpaTest`:** starts only the JPA slice — repositories, entities,
  Flyway. No controllers, no services, no security. Fast.
- **Testcontainers:** `@Testcontainers` + `@Container` spins up a real
  Docker container for the duration of the test class. Your real Flyway
  migrations run against it. What you test is what production gets.
- **Concurrency test pattern:**
    ```java
    int threadCount = 10;
    CountDownLatch start = new CountDownLatch(1);
    CountDownLatch done = new CountDownLatch(threadCount);
    AtomicInteger successCount = new AtomicInteger();

    for (int i = 0; i < threadCount; i++) {
        new Thread(() -> {
            start.await();                       // all threads wait here
            try { joinRoom("ABC123"); successCount.incrementAndGet(); }
            catch (Exception ignored) {}
            finally { done.countDown(); }
        }).start();
    }
    start.countDown();                           // release all threads at once
    done.await();
    assertEquals(1, successCount.get());         // exactly one should have won
    ```

---

## 20. ACTUATOR & OBSERVABILITY

### Spring Boot Actuator

Exposes operational endpoints — health, metrics, info, env — over HTTP.
Already in your `pom.xml`.

- `/actuator/health` — is the app up? Does it have DB/Redis connectivity?
- `/actuator/metrics` — raw metric names and values.
- `/actuator/info` — build info, version, anything you configure.

Expose only what you need in `application.yaml`:

```yaml
management:
    endpoints:
        web:
            exposure:
                include: health,info,metrics
```

Never expose `env` or `beans` in production — they leak configuration and
internal structure.

### Micrometer

Spring Boot's metrics facade. Abstractions over counters, gauges, timers.
Works with any monitoring backend (Prometheus, Datadog, etc.) with a
single dependency swap. `@Timed` on a service method automatically records
its execution time as a metric.

---

## QUICK REFERENCE — "what layer does this belong in?"

| Concern                                  | Layer                                      |
| ---------------------------------------- | ------------------------------------------ |
| Parse/validate the request body          | Argument resolution + `@Valid`             |
| Check if request has a valid JWT         | Filter (`JwtAuthFilter`)                   |
| Check if player is allowed at this URL   | SecurityConfig route rules                 |
| Check if player owns a specific resource | Service layer (domain validation)          |
| All business logic                       | Service                                    |
| Database read/write                      | Repository, called from Service            |
| Start/end a transaction                  | Service (`@Transactional`)                 |
| Cache a result                           | Service (`@Cacheable`)                     |
| Return an HTTP response                  | Controller                                 |
| Push a message over WebSocket            | Service/Engine via `SimpMessagingTemplate` |
| Handle all exceptions uniformly          | `GlobalExceptionHandler`                   |
| Log with context                         | Any layer, MDC set at entry point          |
