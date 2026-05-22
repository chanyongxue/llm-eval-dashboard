# llm-eval-dashboard

AST syntax check · structural similarity vs reference · generation latency · test pass/fail

## Setup

1. Install dependencies:
   ```bash
   python3 -m pip install -r requirements.txt
   ```
2. Copy your Groq API key into `.env` or export it:
   ```bash
   cp .env.example .env
   # then edit .env and paste your GROQ_API_KEY from the notebook
   ```

> Note: `dashboard.js` can store a Groq API key in your browser for convenience, but it still does not generate evaluation data directly. `generate_evaluation.py` or an equivalent notebook must create a JSON results file first.

> If you already have notebook-generated results in JSON format, use the dashboard's `Load results` file picker to load that file directly.
>
> If you only have a notebook file (`.ipynb`) or exported script (`.py`), use the helper script:
>
> ```bash
> python3 notebook_to_results.py path/to/notebook.ipynb --output results.json
> ```
>
> The helper will execute the notebook/script and export the first usable evaluation object it finds, such as `evaluation_df`, `generations_df`, `generation_rows`, or `evaluation_rows`.
>
> Supported JSON shapes include a top-level `entries` array, `evaluation_df`, `generations`, `records`, or pandas JSON output saved with `orient='records'` or `orient='split'.

## Generate evaluation data

```bash
python3 generate_evaluation.py
```

## View the dashboard

Serve the folder locally and open `index.html` in your browser:

```bash
python -m http.server 8000
```

Then visit `http://localhost:8000`.
