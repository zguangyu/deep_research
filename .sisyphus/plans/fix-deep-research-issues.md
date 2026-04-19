# Fix Plan: deep_research_agent.py Issues

## TL;DR

> **Summary**: Fix 12 identified issues in deep_research_agent.py - critical startup crash, duplicate API call, failed status handling, unused retry, UTF-8 truncation, state validation, log rotation, and hygiene.
> **Deliverables**: 8 tasks across 2 waves, test suite added, atomic commits
> **Effort**: Medium
> **Parallel**: YES - Wave 1 (5 tasks), Wave 2 (3 tasks)
> **Critical Path**: Task 1 → Task 2 → Task 3

## Context

### Original Request
User asked to review and fix issues in deep_research_agent.py.

### Issues Found

| # | Severity | Description | Location |
|---|----------|-------------|----------|
| 1 | Critical | TAVILY_API_KEY crashes on startup if missing | L17 |
| 2 | Critical | Duplicate API call - streaming then invoke again | L226-252 |
| 3 | Major | Failed research leaves status="running" forever | L254-258 |
| 4 | Major | retry_with_backoff() defined but never used | L262-282 |
| 5 | Major | Chinese topic truncation breaks filenames | L159 |
| 6 | Major | State file no validation - corrupted JSON silently uses defaults | L106-114 |
| 7 | Major | Log file grows forever without rotation | L25-34 |
| 8-12 | Minor | Broad deps, no KeyboardInterrupt, no timeout, import in loop, hardcoded endpoint | various |

### Metis Review

- **Risk**: Over-engineering could regress current behavior → Keep changes small and isolated
- **Risk**: Integration tests flaky due to external services → Use mocks for unit tests
- **Gap**: No existing test suite → Create tests alongside fixes
- **Approach**: TDD with unit tests per task, integration stubs skippable in CI

## Decisions Needed

Before execution, answer:

1. **Retry library**: Use `tenacity`, `backoff`, or keep existing `retry_with_backoff`?
2. **State schema**: Strict validation (jsonschema) or lightweight approach?
3. **Log rotation**: Size-based (10MB) or time-based (daily)?

**Defaults applied if unanswered**: Keep existing `retry_with_backoff`, lightweight state validation, size-based rotation (10MB).

## Work Objectives

### Core Objective
Fix all identified issues with minimal risk, adding tests to prevent regression.

### Deliverables
- 8 code tasks with fixes
- New test file `tests/test_deep_research_agent.py`
- 8 atomic commits

### Must Have
- No crashes on missing API keys
- No duplicate API calls
- Failed research transitions to "failed" status
- UTF-8 safe filename generation
- Log rotation works
- All fixes covered by tests

### Must NOT Have
- No new external dependencies (use stdlib where possible)
- No behavior changes beyond stated fixes
- No hardcoded endpoints or imports in loops

## Verification Strategy

- **Test decision**: tests-after (create new test file alongside fixes)
- **Framework**: pytest
- **QA policy**: Every task has unit tests; integration tests use mocks
- **Evidence**: .sisyphus/evidence/ directory per task

## Execution Strategy

### Wave 1 (No Dependencies - Run in Parallel)

Wave 1: Tasks 1, 5, 6, 7, 8 (all independent)

### Wave 2 (After Wave 1)

Wave 2: Tasks 2, 3, 4 (depend on Wave 1 logic stabilization)

### Dependency Matrix

| Task | Blocks | Blocked By |
|------|--------|------------|
| 1 | 2 | None |
| 2 | 3, 4 | 1 |
| 3 | - | 2 |
| 4 | - | 2 |
| 5 | - | None |
| 6 | - | None |
| 7 | - | None |
| 8 | - | None |

### Agent Dispatch Summary

Wave 1: 5 tasks, categories: quick (4), unspecified-high (1)
Wave 2: 3 tasks, categories: deep (2), quick (1)

## TODOs

- [x] 1. Harden startup API key handling

  **What to do**: Replace direct `os.environ["TAVILY_API_KEY"]` access with safe getter that raises a clear `SystemExit` with instructions if missing. Apply same pattern to `OPENAI_API_KEY`.

  **Must NOT do**: Don't change the API client initialization logic itself

  **Recommended Agent Profile**:
  - Category: `quick`
  - Skills: [`git-master`]

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: Task 2 | Blocked By: None

  **References**:
  - Code: `deep_research_agent.py:17` - current unsafe access
  - Pattern: `os.environ.get()` with fallback

  **Acceptance Criteria**:
  - [ ] Running script without TAVILY_API_KEY exits with code 1 and message containing "TAVILY_API_KEY"
  - [ ] Running script without OPENAI_API_KEY exits with code 1 and message containing "OPENAI_API_KEY"
  - [ ] With both keys set, startup proceeds normally

  **QA Scenarios**:
  ```
  Scenario: Missing TAVILY_API_KEY
    Tool: Bash
    Steps: env -u TAVILY_API_KEY python deep_research_agent.py -t "test" 2>&1 || echo "EXIT_CODE=$?"
    Expected: Exit code 1, output contains "TAVILY_API_KEY"

  Scenario: Missing OPENAI_API_KEY
    Tool: Bash
    Steps: env -u OPENAI_API_KEY python deep_research_agent.py -t "test" 2>&1 || echo "EXIT_CODE=$?"
    Expected: Exit code 1, output contains "OPENAI_API_KEY"

  Scenario: All keys present
    Tool: Bash
    Steps: python deep_research_agent.py -t "test" --list
    Expected: Runs without crash, exits 0
  ```

  **Commit**: YES | Message: `fix: add startup guard for missing API keys` | Files: `deep_research_agent.py`

- [ ] 2. Fix duplicate API call

  **What to do**: `run_with_logging()` already streams output and presumably completes the research. `run_research()` then calls `agent.invoke()` again, producing duplicate results. Remove the second `agent.invoke()` call in `run_research()` and instead capture the final report from the streaming result or restructure to have a single invocation path.

  **Must NOT do**: Don't remove the streaming output functionality

  **Recommended Agent Profile**:
  - Category: `deep`
  - Skills: [`git-master`, `review-work`]

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: Tasks 3, 4 | Blocked By: Task 1

  **References**:
  - Code: `deep_research_agent.py:226-252` - run_research with duplicate invoke
  - Code: `deep_research_agent.py:168-223` - run_with_logging streaming

  **Acceptance Criteria**:
  - [ ] Research topic produces exactly ONE API call (verify via logging or mock)
  - [ ] Report is correctly saved after streaming completes
  - [ ] No duplicate output or overwrites

  **QA Scenarios**:
  ```
  Scenario: Single research invocation
    Tool: interactive_bash
    Steps: python -c "
import logging
import deep_research_agent as d
logging.basicConfig(level=logging.INFO)
# Mock agent.stream and agent.invoke to count calls
original_stream = d.agent.stream
original_invoke = d.agent.invoke
stream_count = [0]
invoke_count = [0]
def mock_stream(*args, **kwargs):
    stream_count[0] += 1
    return []
def mock_invoke(*args, **kwargs):
    invoke_count[0] += 1
    return {'messages': [type('obj', (object,), {'content': '# Test Report\n\nTest'})()]}
d.agent.stream = mock_stream
d.agent.invoke = mock_invoke
d.run_research('test topic', resume=False)
print(f'stream_calls={stream_count[0]}, invoke_calls={invoke_count[0]}')
"
    Expected: stream_calls >= 1, invoke_calls == 0
  ```

  **Commit**: YES | Message: `fix: remove duplicate API call in research flow` | Files: `deep_research_agent.py`

- [ ] 3. Fix research status on failure

  **What to do**: In `run_research()`, when exception occurs, ensure status is set to "failed" before re-raising. Currently `state.save_topic_progress(topic, "running")` is called at start but failure path may not update status correctly.

  **Must NOT do**: Don't change the status transition logic for success cases

  **Recommended Agent Profile**:
  - Category: `deep`
  - Skills: [`git-master`, `review-work`]

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: None | Blocked By: Task 2

  **References**:
  - Code: `deep_research_agent.py:226-259` - run_research try/except

  **Acceptance Criteria**:
  - [ ] When research fails, status is "failed" (not "running")
  - [ ] `--list` shows correct status after failure
  - [ ] Error message is preserved in state

  **QA Scenarios**:
  ```
  Scenario: Failed research shows correct status
    Tool: interactive_bash
    Steps: |
      python -c "
import deep_research_agent as d
d.state.state = {'topics': {'test_topic': {'status': 'running', 'topic': 'test_topic', 'error': ''}}}
d.state.save_state()
# Simulate failure
try:
    d.run_research('test_topic', resume=True)
except Exception:
    pass
import json
with open('research_state.json') as f:
    state = json.load(f)
print(state['topics']['test_topic'].get('status'))
"
    Expected: status == "failed"
  ```

  **Commit**: YES | Message: `fix: set status to failed when research errors` | Files: `deep_research_agent.py`

- [ ] 4. Wire retry_with_backoff into API calls

  **What to do**: Apply `retry_with_backoff()` wrapper to `agent.stream()` call in `run_with_logging()`. Use existing function (3 retries, 5s initial delay, 2x backoff).

  **Must NOT do**: Don't create new retry library dependency

  **Recommended Agent Profile**:
  - Category: `quick`
  - Skills: [`git-master`]

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: None | Blocked By: Task 2

  **References**:
  - Code: `deep_research_agent.py:262-282` - existing retry_with_backoff (unused)
  - Code: `deep_research_agent.py:176` - agent.stream() call

  **Acceptance Criteria**:
  - [ ] Transient failures trigger retry (test with mock)
  - [ ] Max retries respected
  - [ ] Final exception after all retries exhausted

  **QA Scenarios**:
  ```
  Scenario: Retry on transient failure
    Tool: interactive_bash
    Steps: |
      python -c "
import deep_research_agent as d
call_count = [0]
def failing_stream(*args, **kwargs):
    call_count[0] += 1
    if call_count[0] < 3:
        raise ConnectionError('transient')
    return []
d.agent.stream = failing_stream
try:
    d.retry_with_backoff(lambda: d.agent.stream({}, stream_mode='messages', subgraphs=True, version='v2'))
except ConnectionError:
    pass
print(f'call_count={call_count[0]}')
"
    Expected: call_count == 3
  ```

  **Commit**: YES | Message: `feat: apply retry backoff to agent.stream calls` | Files: `deep_research_agent.py`

- [ ] 5. Fix UTF-8 safe topic truncation

  **What to do**: Replace `safe_topic[:50]` with UTF-8 safe truncation: `safe_topic.encode('utf-8')[:50].decode('utf-8', errors='ignore')`

  **Must NOT do**: Don't change the character limit value (50)

  **Recommended Agent Profile**:
  - Category: `quick`
  - Skills: [`git-master`]

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: None | Blocked By: None

  **References**:
  - Code: `deep_research_agent.py:159` - current slicing

  **Acceptance Criteria**:
  - [ ] Chinese topic "人工智能发展趋势研究" produces valid filename
  - [ ] Emoji topic "🚀技术趋势2026" produces valid filename
  - [ ] ASCII topic truncated correctly at 50 chars

  **QA Scenarios**:
  ```
  Scenario: Chinese topic filename
    Tool: Bash
    Steps: python -c "
import re
topic = '人工智能发展趋势研究与分析'
safe_topic = re.sub(r'[<>:\"/\\\\|?*]', '', topic)
safe_topic = safe_topic.encode('utf-8')[:50].decode('utf-8', errors='ignore')
print(repr(safe_topic))
# Verify it's valid UTF-8
safe_topic.encode('utf-8')
print('valid')
"
    Expected: Output shows valid Chinese string, no UnicodeDecodeError

  Scenario: Mixed content truncation
    Tool: Bash
    Steps: python -c "
import re
topic = 'A' * 60 + '中' * 10
safe_topic = re.sub(r'[<>:\"/\\\\|?*]', '', topic)
safe_topic = safe_topic.encode('utf-8')[:50].decode('utf-8', errors='ignore')
print(f'len={len(safe_topic)}, bytes={len(safe_topic.encode(\"utf-8\"))}')
"
    Expected: Byte length <= 50, no half-character cut
  ```

  **Commit**: YES | Message: `fix: use UTF-8 safe truncation for topic filenames` | Files: `deep_research_agent.py`

- [ ] 6. Add state file validation

  **What to do**: In `ResearchState._load()`, add try/except around JSON parsing. If invalid, log error and return default structure instead of silently continuing with empty state.

  **Must NOT do**: Don't delete corrupted state file automatically

  **Recommended Agent Profile**:
  - Category: `quick`
  - Skills: [`git-master`]

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: None | Blocked By: None

  **References**:
  - Code: `deep_research_agent.py:106-114` - _load method

  **Acceptance Criteria**:
  - [ ] Valid JSON state file loads correctly
  - [ ] Corrupted JSON causes error log and uses defaults
  - [ ] Default structure has required keys: topics (dict), version (int)

  **QA Scenarios**:
  ```
  Scenario: Corrupted state file
    Tool: Bash
    Steps: |
      echo '{invalid json content' > research_state.json
      python -c "
import deep_research_agent as d
d.state.load_state()
print('topics' in d.state.state)
" 2>&1 | grep -i "error\|warning\|traceback"
    Expected: Error logged about JSON parse failure, topics key exists

  Scenario: Valid state file
    Tool: Bash
    Steps: |
      echo '{"topics": {}, "version": 1}' > research_state.json
      python -c "
import deep_research_agent as d
d.state.load_state()
print(d.state.state.get('topics'))
"
    Expected: Empty dict printed
  ```

  **Commit**: YES | Message: `fix: validate JSON when loading state file` | Files: `deep_research_agent.py`

- [ ] 7. Add log rotation

  **What to do**: Replace `logging.FileHandler(LOG_FILE)` with `logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=10_485_760, backupCount=5)`.

  **Must NOT do**: Don't change log format or level

  **Recommended Agent Profile**:
  - Category: `quick`
  - Skills: [`git-master`]

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: None | Blocked By: None

  **References**:
  - Code: `deep_research_agent.py:25-34` - logging setup

  **Acceptance Criteria**:
  - [ ] Log file rotates at 10MB
  - [ ] Maximum 5 backup files kept
  - [ ] Current log continues writing after rotation

  **QA Scenarios**:
  ```
  Scenario: Log rotation trigger
    Tool: interactive_bash
    Steps: |
      python -c "
import logging, logging.handlers, os
handler = logging.handlers.RotatingFileHandler(
    'test_rotating.log', maxBytes=100, backupCount=3)
logger = logging.getLogger('test')
logger.addHandler(handler)
logger.setLevel(logging.INFO)
for i in range(20):
    logger.info('x' * 50)
handler.close()
import glob
files = glob.glob('test_rotating.log*')
print(sorted(files))
for f in files:
    os.remove(f)
"
    Expected: test_rotating.log and test_rotating.log.1, .2, .3 exist
  ```

  **Commit**: YES | Message: `feat: add rotating log handler to prevent unbounded growth` | Files: `deep_research_agent.py`

- [ ] 8. General hygiene improvements

  **What to do**:
  - Move `import time` to top-level (L275)
  - Add `KeyboardInterrupt` handling in main loop
  - Make base_url configurable via env var
  - Verify dependency versions are reasonable

  **Must NOT do**: Don't add new dependencies

  **Recommended Agent Profile**:
  - Category: `unspecified-high`
  - Skills: [`git-master`, `review-work`]

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: None | Blocked By: None

  **References**:
  - Code: `deep_research_agent.py:275` - import in function
  - Code: `deep_research_agent.py:18` - hardcoded base_url

  **Acceptance Criteria**:
  - [ ] `import time` at top of file
  - [ ] Ctrl+C during interactive input exits gracefully
  - [ ] MINIMAX_BASE_URL env var overrides default base_url

  **QA Scenarios**:
  ```
  Scenario: Import at top level
    Tool: Bash
    Steps: head -20 deep_research_agent.py | grep -n 'import time'
    Expected: import time appears before any function definitions

  Scenario: Base URL override
    Tool: Bash
    Steps: MINIMAX_BASE_URL='https://custom.example.com/v1' python -c "
from deep_research_agent import model
print(model.base_url)
"
    Expected: https://custom.example.com/v1
  ```

  **Commit**: YES | Message: `chore: hygiene improvements - imports, interrupt handling, configurable base_url` | Files: `deep_research_agent.py`

## Final Verification Wave

- [ ] F1. Plan Compliance Audit — oracle
- [ ] F2. Code Quality Review — unspecified-high
- [ ] F3. Real Manual QA — unspecified-high
- [ ] F4. Scope Fidelity Check — deep

## Commit Strategy

| Task | Branch | Message |
|------|--------|---------|
| 1 | fix/startup-api-key-guard | `fix: add startup guard for missing API keys` |
| 2 | fix/duplicate-api-call | `fix: remove duplicate API call in research flow` |
| 3 | fix/research-status-failure | `fix: set status to failed when research errors` |
| 4 | feat/retry-backoff-wired | `feat: apply retry backoff to agent.stream calls` |
| 5 | fix/utf8-filename-truncation | `fix: use UTF-8 safe truncation for topic filenames` |
| 6 | fix/state-file-validation | `fix: validate JSON when loading state file` |
| 7 | feat/log-rotation | `feat: add rotating log handler to prevent unbounded growth` |
| 8 | chore/hygiene-improvements | `chore: hygiene improvements - imports, interrupt handling, configurable base_url` |

## Success Criteria

- All 8 tasks complete with tests passing
- No duplicate API calls
- Missing API keys produce clear error messages
- UTF-8 filenames work correctly
- Log rotation functional
- State file corruption handled gracefully
- Status transitions are correct on failure
- Retry backoff wired to network calls
