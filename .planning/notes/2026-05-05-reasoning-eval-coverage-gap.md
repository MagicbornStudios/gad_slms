# Eval suite needs intermediate-step scoring, not just final-answer match

Per slm-learning-018 (high reasoning > crystallized knowledge), our current eval matrix scores final answers only. To validate the reasoning-quality bet we need: (1) intermediate-step correctness on math (parse <think> blocks, verify each algebraic step), (2) test-pass-rate per problem on code (HumanEval), (3) tool-call structural correctness on GAD-tool eval (right command + right flags + right args, not just icontains). Wire as scripts/eval_reasoning_quality.py once Stage 2.5 produces a checkpoint worth probing.
