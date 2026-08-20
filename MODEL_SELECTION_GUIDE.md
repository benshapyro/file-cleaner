# Historical model-selection notes

> This describes the former AI-first prototype. The current tool keeps AI off by default and treats it as advisory only. See README.md for supported behavior.

## Current Implementation: GPT-4.1 Mini (Updated April 2025)

### GPT-4.1 Mini is Now the Optimal Choice

As of April 2025, **GPT-4.1 Mini has replaced GPT-4o-mini as the best value model**. Here's why:

#### GPT-4.1 Mini Advantages
- **83% cheaper** than GPT-4o: $0.40/$1.60 per million tokens (vs $2.50/$10)
- **1 million token context window** (vs 128K for GPT-4o-mini)
- **Nearly half the latency** of GPT-4o
- **Matches or exceeds GPT-4o performance** in many benchmarks
- **More recent knowledge cutoff** (June 2024 vs October 2023)
- **Better structured output support** with strict schema adherence

#### What We're Actually Doing
1. Analyzing file **metadata** only (names, sizes, dates)
2. Simple categorization based on patterns
3. Processing small batches (20 files at a time)
4. Making straightforward decisions (safe to delete / might be important / keep)

#### Why We Don't Need Reasoning Models (o3/o4-mini)
- **No complex multi-step reasoning required**: We're not solving puzzles or planning sequences
- **No tool orchestration**: We're not calling multiple APIs or tools
- **Simple decision tree**: Our logic is essentially "if filename contains X and age > Y, then suggest deletion"
- **Cost efficiency**: o3/o4-mini cost more without providing benefits for this use case

#### Why We Don't Need Large Context Models (GPT-4.1)
- **Small context usage**: We only send ~20 filenames at a time
- **No file content analysis**: We never read file contents
- **Sufficient token window**: Even GPT-4o-mini's context window far exceeds our needs

## When to Consider Upgrading

### Scenario 1: Enhanced Duplicate Detection
**Current**: Check filenames for patterns like "(1)", "(2)"
**Enhanced**: Read file contents and compare

**Recommended Model**: Still GPT-4o-mini
- File hashing doesn't need AI
- Content comparison is algorithmic, not AI-driven

### Scenario 2: Content-Based Importance Detection
**Current**: Judge importance by filename
**Enhanced**: Read document contents to assess importance

**Recommended Model**: GPT-4o or GPT-4.1
- Need larger context for document analysis
- Better understanding of content relevance

### Scenario 3: Complex Organization Rules
**Current**: Simple category-based organization
**Enhanced**: Multi-factor decision making with dependencies

**Recommended Model**: o4-mini
- Complex reasoning about file relationships
- Planning optimal organization structure
- Handling edge cases with nuanced logic

### Scenario 4: Autonomous Cleanup Agent
**Current**: User confirms each category
**Enhanced**: AI makes autonomous decisions with explanations

**Recommended Model**: o3
- Highest reasoning capability for trust
- Better at explaining decisions
- More reliable for autonomous operation

## Cost/Benefit Analysis

| Use Case | Current Cost | With o4-mini | With o3 | Benefit |
|----------|--------------|--------------|---------|---------|
| Basic cleanup | $0.01 | $0.02 | $0.10 | None |
| Content analysis | N/A | $0.05 | $0.25 | Moderate |
| Complex reasoning | N/A | $0.05 | $0.25 | High |
| Autonomous agent | N/A | $0.10 | $0.50 | Very High |

## Recommendations

### Keep Current Implementation
✅ **GPT-4o-mini is perfect for the current scope**
- Fast responses
- Minimal cost
- Sufficient accuracy
- No wasted capabilities

### Future Enhancements Priority
1. **File type/size rules** (implemented) - No model change needed
2. **Hash-based duplicate detection** - No model change needed
3. **Protected patterns** (implemented) - No model change needed
4. **Content preview** for text files - Consider GPT-4o
5. **Complex reasoning** - Consider o4-mini

## Configuration for Different Models

If you want to experiment with different models, update `config.py`:

```python
# For better content understanding (2x cost)
AI_MODEL = "gpt-4o"

# For complex reasoning (3x cost)
AI_MODEL = "o4-mini"

# For best reasoning (10x cost)
AI_MODEL = "o3"
```

## Conclusion

The beauty of good engineering is using the right tool for the job. For analyzing file metadata and making simple categorization decisions, GPT-4o-mini provides excellent results at minimal cost. The reasoning models (o3/o4-mini) would be like using a sports car for grocery shopping—impressive but unnecessary.

Save the advanced models for when you truly need:
- Multi-step reasoning
- Content understanding
- Complex decision trees
- Autonomous operation
