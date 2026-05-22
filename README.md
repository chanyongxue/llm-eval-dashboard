# llm-eval-dashboard

AST syntax check · structural similarity vs reference · generation latency · test pass/fail

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Copy your Groq API key into `.env` or export it:
   ```bash
   cp .env.example .env
   # then edit .env and paste your GROQ_API_KEY from the notebook
   ```

## Generate evaluation data

Run the Python generator to produce `results.json` for the dashboard:

```bash
python generate_evaluation.py
```

## View the dashboard

Serve the folder locally and open `index.html` in your browser:

```bash
python -m http.server 8000
```

Then visit `http://localhost:8000`.
