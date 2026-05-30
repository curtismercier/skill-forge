---
name: black-box
description: Test scripts, server management, and headless components by controlling inputs and verifying outputs. Use whenever you're writing tests for a component, script, or service where you want to verify behavior without coupling to internals. Covers: vitest/jsdom setup, extracting pure functions from UI components, mocking fetch/sessionStorage/router, testing bash/Python scripts via subprocess, and verify-before-claim patterns for deploy/ops checks. NOT for integration tests that need a real browser or database.
metadata:
  author: Soma
  version: "1.0.0"
  source-style: authored
  created: 2026-05-30
  last_reviewed: 2026-05-30
  review_interval_days: 180
---

# black-box — test inputs, verify outputs, ignore internals

**The black-box principle:** a test that knows about internals breaks when internals change. A test that only knows inputs and outputs survives refactors.

This skill captures the pattern from the arzadon-handoff popup testing session (s01-1668a8): we extracted pure targeting functions from a React component, unit-tested them heavily, then tested the component shell with mocked side effects. The same approach applies to shell scripts, API wrappers, and deploy verification.

## When to use this skill

Use this skill when:

- **You're testing a component** and it has nontrivial logic embedded inside (`shouldShowOnPage`, `pathMatches`, data transformations)
- **You're testing a script** (bash, Python, Node) and want to verify its output given specific inputs/environment
- **You're writing a deploy/ops check** and need to verify a server state (container running, config correct, endpoint responding)
- **Someone says "write tests"** and you need to decide what to test and how

Do NOT use this skill for:

- Integration tests that need a real browser (Playwright, Cypress)
- Database-specific query testing (use your ORM's test helpers)
- Load/performance testing

## Core pattern: progressive extraction

The single most important move in black-box testing:

```
┌──────────────────────────────────────────┐
│  1. Pure function logic (testable)       │ ← extract first
│     → pathMatches, shouldShowOnPage      │
├──────────────────────────────────────────┤
│  2. Component shell (mock side effects)  │ ← then test consumer
│     → rendering, interactions, fetch     │
├──────────────────────────────────────────┤
│  3. API / route layer (mock framework)   │ ← optional, lower value
│     → request validation, error codes    │
└──────────────────────────────────────────┘
```

**Never test layer 1 through layer 2.** Extract the logic, test it directly, then trust the component uses it correctly (one integration test per interaction is enough).

## How

### Step 1: identify what to extract

Look for pure functions hiding inside components:

- Path matching, string parsing, date formatting
- Visibility/access logic ("should X show?")
- Data transformation (API response → display format)
- Validation rules

These are pure functions that take inputs, return outputs, and have zero side effects. Extract them into a `src/lib/` or `src/utils/` module.

**From the session that spawned this skill:** `MothersDayPopup.tsx` had `pathMatches()` and `shouldShowOnPage()` defined as local functions. We extracted them to `src/lib/popup-targeting.ts` — 40 lines that got 37 unit tests covering every edge case.

### Step 2: test the extracted functions first

Use `describe`/`it` blocks that cover:

```
- Happy path (exact match, wildcard match, include mode)
- Boundary (root path, empty string, trailing slashes)
- Always-excluded routes (dashboard, login, account)
- Mode edge cases (empty paths → show all)
- Non-matching cases
```

These tests run in milliseconds and catch 90% of logic bugs. Example structure:

```typescript
describe('pathMatches', () => {
  it('exact match', () => { ... });
  it('wildcard prefix match', () => { ... });
  it('trailing slash normalization', () => { ... });
});

describe('shouldShowOnPage — always-excluded routes', () => {
  it('hides on /dashboard', () => { ... });
  it('hides on /login', () => { ... });
});
```

### Step 3: test the component shell with mocks

Once the logic is extracted, the component becomes a thin shell. Test it with:

**fetch mock pattern:**
```typescript
beforeEach(() => {
  globalThis.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(mockConfig),
  });
});
afterEach(() => { vi.restoreAllMocks(); });
```

**sessionStorage mock** — jsdom ships it, just set/clear in beforeEach.

**router mock** — next/navigation's `usePathname` can be mocked at the module level:
```typescript
vi.mock('next/navigation', () => ({ usePathname: () => mockPathname }));
```

**Component test structure:**
```
- Does the component render after loading? (waitFor + getByDisplayValue)
- Do interactions update the UI? (fireEvent.click, check text changed)
- Do mode toggles show/hide conditional UI?
```

Test interactions with `fireEvent` (not `userEvent` — it's lighter and doesn't need an extra dependency). One test per interaction path, no more.

### Step 4: API routes — extract validation first, then the route is trivial

**Don't mock the framework — extract the logic instead.**

Route handlers usually combine: (a) pure validation/transformation logic, (b) a thin framework wrapper. Extract (a) into your lib, test it directly, and the wrapper becomes too trivial to need testing.

**From the session that spawned this skill:** the PUT route had an inline `sanitizePopupConfig()` function that clamps values, filters paths, and defaults booleans. We extracted it into `popup-targeting.ts` — got 10 unit tests, zero framework mocking. The route handler is now 8 lines:

```typescript
export async function PUT(request: Request) {
  const body = await request.json();
  const safe = sanitizePopupConfig(body);                              // ← tested
  await writeFile(CONFIG_PATH, JSON.stringify(safe, null, 2) + '\\n');
  return NextResponse.json(safe);
}
```

**Rule:** if the route has more validation than I/O boilerplate, extract the validation. If it's just a proxy (read → return, receive → save), skip route-level tests.

### Step 5: run tests on change

```bash
pnpm test                     # full suite
pnpm test -- --watch          # watch mode during dev
pnpm test -- src/path/        # scope to one directory
```

## Vitest setup checklist

Add these to your project once:

1. **vitest.config.ts** — jsdom environment, path aliases, setup file
   ```typescript
   test: {
     environment: 'jsdom',
     globals: true,
     setupFiles: ['./vitest.setup.ts'],
   }
   ```

2. **vitest.setup.ts** — jest-dom matchers
   ```typescript
   import '@testing-library/jest-dom';
   ```

3. **package.json scripts**
   ```json
   "test": "vitest run",
   "test:watch": "vitest"
   ```

## Black-box testing for scripts (bash/Python)

Same principle applies: control inputs, capture outputs.

```bash
# bash — set env vars, capture stdout
OUTPUT=$(MY_VAR=value ./script.sh --flag input)
assert_equals "$OUTPUT" "expected"
echo "$?"  # exit code
```

```python
# Python subprocess
import subprocess
result = subprocess.run(['python', 'script.py', '--flag'],
    capture_output=True, text=True, env={'MY_VAR': 'value'})
assert result.returncode == 0
assert 'expected' in result.stdout
```

For deploy verification, curl the endpoint and check response headers/content:
```bash
curl -sI https://example.com | grep -q "200 OK"
curl -s https://example.com | grep -q "<!-- fingerprint: cycle-123 -->"
```

## Directory convention

```
src/app/dashboard/popup/         # component + page
  __tests__/                      # collocated test suite
    popup-targeting.test.ts       # unit tests for extracted logic
    popup-editor.test.tsx         # component tests with mocks
    popup-api.test.ts             # (optional) route handler tests
```

Tests live next to what they test. Three files for three test surfaces. This is the pattern; follow it.

## Anti-patterns

- **Testing internals.** Don't export private functions just to test them. Extract them to a shared module instead.
- **Mocking too much.** If you need 5 mocks for one component, the component is doing too much. Extract.
- **Golden-file testing component output.** Test behavior (user clicks → text changes), not DOM structure (class names, nesting).
- **Over-mocking fetch.** One mock per test suite, not per test. Reset between tests, don't recreate.
- **Testing through the wrong layer.** Don't test path matching through a rendered popup. Test the function directly.
