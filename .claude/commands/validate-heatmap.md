# /validate-heatmap - Visual Heatmap Validation

Iterative visual validation of liquidation heatmap at `http://localhost:8000/heatmap.html`.

## Usage
```
/validate-heatmap [--max-rounds 5] [--reference screenshots/baseline.png]
```

## Repo Context

- **Frontend**: `frontend/heatmap.html` (Plotly.js)
- **API**: FastAPI at `localhost:8000` (run via `uv run uvicorn api.main:app`)
- **DB**: `/media/sam/2TB-NVMe/liquidationheatmap_db/liquidations.duckdb`

## Orchestration Flow

```
ROUND N
  │
  ├─► mcp__playwright__browser_navigate("http://localhost:8000/heatmap.html")
  ├─► mcp__playwright__browser_take_screenshot()
  ├─► Analyze Plotly heatmap:
  │     - Color scale (Viridis/thermal gradient)
  │     - Price axis (Y) - liquidation levels
  │     - Time axis (X) - bucket intervals
  │     - Hover tooltips functional
  │     - No Plotly error overlays
  ├─► mcp__chrome-devtools__list_console_messages()
  │     - Check for JS errors
  ├─► Score (0-100%)
  └─► PASS (>= 95%) | FAIL → next round
```

## Agent Delegation

```python
Task(
    subagent_type="alpha-visual",
    prompt="""
    Validate heatmap at http://localhost:8000/heatmap.html

    MCP Tools:
    - mcp__playwright__browser_navigate
    - mcp__playwright__browser_take_screenshot
    - mcp__chrome-devtools__list_console_messages
    - mcp__chrome-devtools__evaluate_script

    Validation criteria:
    1. Plotly heatmap renders (no blank/error state)
    2. Color gradient visible (liquidation intensity)
    3. Both axes labeled correctly
    4. No console errors
    5. Data loaded (not "Loading..." state)

    Continue until PASS or max {max_rounds} rounds.
    """
)
```

## Output

```markdown
### Round 1/5
- Navigate: http://localhost:8000/heatmap.html ✓
- Screenshot: captured
- Plotly render: PASS
- Console errors: 0
- Score: 98%
- Decision: PASS

### Result: SUCCESS
```
