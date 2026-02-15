# Agent Specialization Spectrum Experiment

**Goal**: Find the sweet spot for agent scope — how narrow before integration friction? How broad before quality drops?

**Date**: Feb 15-16, 2026

## Hypothesis
There's a U-curve of integration cost:
- **Too broad** (1 agent = everything): Low coordination cost, but output quality drops because context is diluted
- **Too narrow** (1 agent per function): High quality per piece, but stitching together is expensive and outputs may contradict
- **Sweet spot**: Agents scoped to a coherent domain (QA, Security, Docs) where they have enough context to make good decisions but not so much they lose focus

## Experiment Design

### Round 1: Broad (1 agent does everything)
Spawn ONE agent with the task:
"You are the full-stack review agent. Do a QA test, security audit, and write documentation for the key rotation endpoint."

Measure:
- Quality of each section (1-5)
- Did it find the same bugs the specialist agents found?
- Token usage
- Runtime
- Integration effort (how easy to use the output?)

### Round 2: Narrow (3 hyper-specific agents)
Spawn THREE agents, each doing one narrow slice of the key rotation endpoint:
1. "Test only the key rotation happy path and error cases"
2. "Audit only the key rotation code for security issues"
3. "Document only the key rotation endpoint"

Measure:
- Quality of each piece (1-5)
- Do they contradict each other?
- Token usage (total)
- Runtime (total, with parallelism)
- Integration effort (how much work to stitch together?)

### Round 3: Our Current Model (domain specialists)
This is already done — QA, Security, Docs agents from tonight.
Use those results as the baseline.

## Scoring Rubric

### Quality (1-5)
- 5: Found real bugs, actionable recommendations, ready to act on
- 4: Solid coverage, minor gaps, mostly actionable
- 3: Surface level, obvious stuff, would need follow-up
- 2: Missed important things, some incorrect findings
- 1: Useless or actively misleading

### Integration (1-5)
- 5: Drop-in, no coordination needed
- 4: Minor formatting cleanup
- 3: Had to resolve some contradictions or fill gaps
- 2: Significant rework needed to combine outputs
- 1: Easier to redo than to integrate

## Expected Outcome
Domain specialists (current model) will score highest on quality × integration. Broad agent will be fastest but miss depth. Narrow agents will find the most but cost the most to integrate.

## Run Notes
(Fill in during execution)
