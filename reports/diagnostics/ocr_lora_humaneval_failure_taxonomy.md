# HumanEval failure taxonomy — 7B base vs 7B + OCR LoRA

Per `slm-learning-107`. Generated from full per-case completions persisted via `eval_adapter.py persist_run_id`.

## Failure counts by bucket

| Bucket | 7B base | 7B + OCR LoRA | Δ |
|---|---|---|---|
| A_think_truncation | 0 | 1 | +1 |
| B_code_truncated | 0 | 0 | 0 |
| C_wrong_function_signature | 0 | 0 | 0 |
| D_full_script_not_function | 0 | 0 | 0 |
| E_competitive_style | 0 | 0 | 0 |
| F_markdown_prose_pollution | 1 | 0 | -1 |
| G_indentation_prefix_bug | 33 | 81 | +48 |
| H_genuine_algorithm_fail | 0 | 0 | 0 |
| I_evaluator_bug | 24 | 32 | +8 |
| **TOTAL FAILURES** | **58** | **114** | **+56** |

7B base: 58/164 failed
7B LoRA: 114/164 failed

## Diagnostic interpretation

Look at where the LoRA's failures CONCENTRATE relative to base:

- **G_indentation_prefix_bug**: LoRA has +48 more failures here. This is a hypothesis confirmed.
- **I_evaluator_bug**: LoRA has +8 more failures here. This is a hypothesis confirmed.
- **A_think_truncation**: LoRA has +1 more failures here. This is a hypothesis confirmed.

## Sample failures by bucket

### A_think_truncation

**HumanEval/83** — open <think> never closed

```
<think>
Okay, I need to solve this problem where I have to find how many n-digit positive integers start or end with 1. Let's think about it step by step.

First, let's understand what an n-digit numb
```

_judge: Traceback (most recent call last):
  File "/tmp/tmp73k8g6hc.py", line 26, in <module>
    check(starts_one_ends)
  File "/tmp/tmp73k8g6hc.py", line 16, in check
    assert candidate(1) == 1
          _

### G_indentation_prefix_bug

**HumanEval/0** —   File "/tmp/tmp14cu0llm.py", line 19
    return False
                ^
IndentationError: unindent does not match any o

```
```python
    for i in range(len(numbers)):
        for j in range(i + 1, len(numbers)):
            if abs(numbers[i] - numbers[j]) < threshold:
                return True
    return False
```
```

_judge:   File "/tmp/tmp14cu0llm.py", line 19
    return False
                ^
IndentationError: unindent does not match any outer indentation level
_

**HumanEval/2** — return outside function

```
```python
    return number - int(number)
```
```

_judge:   File "/tmp/tmpohb4i25j.py", line 15
    return number - int(number)
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^
SyntaxError: 'return' outside function
_

**HumanEval/3** — return outside function

```
```python
balance = 0
for op in operations:
    balance += op
    if balance < 0:
        return True
return False
```
```

_judge:   File "/tmp/tmpxu6dwjdz.py", line 20
    return True
    ^^^^^^^^^^^
SyntaxError: 'return' outside function
_

### I_evaluator_bug

**HumanEval/6** — unclassified: '  File "/tmp/tmph7o8au5m.py", line 15\n    return [max(map(len, g.split(\' \'))) fo'

```
```python
    return [max(map(len, g.split(' '))) for g in paren_string.split()]
```
```

_judge:   File "/tmp/tmph7o8au5m.py", line 15
    return [max(map(len, g.split(' '))) for g in paren_string.split()]
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
SyntaxError: 'return_

**HumanEval/17** — unclassified: '  File "/tmp/tmpm0s3du4b.py", line 20\n    return [4 if note == \'o\' else 2 if not'

```
```python
    return [4 if note == 'o' else 2 if note == 'o|' else 1 for note in music_string.split()]
```
```

_judge:   File "/tmp/tmpm0s3du4b.py", line 20
    return [4 if note == 'o' else 2 if note == 'o|' else 1 for note in music_string.split()]
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^_

**HumanEval/18** — unclassified: '  File "/tmp/tmp1g0m56t5.py", line 15\n    return len([i for i in range(len(strin'

```
```python
    return len([i for i in range(len(string)) if string.startswith(substring, i)])
```
```

_judge:   File "/tmp/tmp1g0m56t5.py", line 15
    return len([i for i in range(len(string)) if string.startswith(substring, i)])
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^_
