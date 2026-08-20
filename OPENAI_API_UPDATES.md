# Historical OpenAI API notes

> This is implementation history, not current setup guidance. Current AI behavior is optional, advisory, and configured through macOS Keychain.

## Summary of Key Changes

### 1. New Models Available

#### Latest Reasoning Models (April 2025)
- **o3**: Most advanced reasoning model with superior performance
  - Best for: Complex reasoning, multi-step problems, visual analysis
  - Cost: High

- **o4-mini**: Efficient reasoning model
  - Best for: Balance of performance and cost
  - Cost: Low

#### Current Best Value Models
- **gpt-4o-mini**: Best overall value (recommended for most use cases)
- **gpt-4o**: Premium performance at moderate cost

### 2. API Changes

#### New Responses API
OpenAI has introduced a new **Responses API** alongside the existing Chat Completions API:
- Better for tool use and state management
- Server-side conversation state management
- Built-in tools (web search, file search, computer use)

However, the Chat Completions API remains supported indefinitely.

#### Current Implementation Status
Our implementation uses the **Chat Completions API**, which is still fully supported and appropriate for our use case.

### 3. Best Practices for Function Calling

Based on OpenAI's latest guidance for o3/o4-mini models:

#### Context Setting
```python
messages = [
    {"role": "system", "content": "Clear, specific instructions"},
    {"role": "user", "content": prompt},
]
```

#### Response Format
Use `response_format={"type": "json_object"}` to ensure JSON responses when needed.

#### Safety Features
1. **Never auto-delete without confirmation**
2. **Time-based protection** (MIN_AGE_FOR_DELETION)
3. **Protected patterns and whitelisting**
4. **Detailed logging of all actions**

### 4. Implemented Updates

✅ **Updated to gpt-4o-mini** - Best value model
✅ **Added response_format** for reliable JSON parsing
✅ **Implemented safety checks**:
   - Protected file patterns
   - Minimum age before deletion (7 days)
   - Whitelisted filenames
✅ **Enhanced configuration** with model options

### 5. Cost Considerations

| Model | Input Cost | Output Cost | Best For |
|-------|------------|-------------|----------|
| gpt-3.5-turbo | Lowest | Lowest | Basic tasks |
| gpt-4o-mini | Low | Low | **Most use cases** ✓ |
| gpt-4o | Medium | Medium | Complex tasks |
| o4-mini | Low | Low | Reasoning tasks |
| o3 | High | High | Advanced reasoning |

### 6. Future Considerations

#### Potential Migration to Responses API
While not necessary now, future benefits could include:
- Server-side state management
- Built-in web search for file information
- Simplified multi-turn conversations

#### Enhanced Duplicate Detection
The `duplicate_detector.py` module is ready to implement:
- MD5/SHA hashing for true duplicate detection
- Content-based comparison
- Smart recommendations for which duplicates to keep

### 7. Current Implementation Strengths

Our implementation already follows many best practices:
- ✅ Safe deletion (trash, not permanent)
- ✅ Multiple confirmation levels
- ✅ Detailed logging
- ✅ Dry-run mode
- ✅ Organization mode (not just deletion)
- ✅ AI-assisted categorization
- ✅ Configurable safety settings

### 8. Recommendations

1. **Keep using Chat Completions API** - It's stable and meets our needs
2. **Monitor costs** - gpt-4o-mini provides excellent value
3. **Consider o4-mini** for future enhancements requiring better reasoning
4. **Implement duplicate detection** when ready for enhanced functionality

## References

- [OpenAI Platform Docs](https://platform.openai.com/docs)
- [o3/o4-mini Function Calling Guide](https://cookbook.openai.com/examples/o-series/o3o4-mini_prompting_guide)
- [Responses API Guide](https://cookbook.openai.com/examples/responses_api/responses_example)
