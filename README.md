# ToxExplain — Cognito

> Layering curated mechanistic knowledge onto toxicity predictions to improve interpretability and move from black-box outputs to actionable science.

## What this does

ToxExplain takes a SMILES string as input and returns:
- A toxicity prediction (currently ProTox-II, will be replaced by our own model)
- Curated mechanistic evidence from withdrawn drugs (Groups A & B)
- LLM-generated interpretability rules explaining *why* a compound may be toxic
- A combined explainability summary linking prediction to mechanism

## Project structure

```
toxexplain/
│
├── frontend/                        # STREAM 3 — Explainable UI (Vue 3 + Vite)
│   ├── src/
│   │   ├── components/
│   │   │   ├── SmilesInputForm.vue
│   │   │   ├── PredictionSummaryCard.vue
│   │   │   ├── CuratedEvidencePanel.vue
│   │   │   ├── MechanismOverlayPanel.vue
│   │   │   ├── RuleMatchCard.vue
│   │   │   ├── EndpointComparisonPanel.vue
│   │   │   └── EvidenceLevelBadge.vue
│   │   ├── views/
│   │   │   ├── InputView.vue        # Screen 1: SMILES input
│   │   │   ├── ResultsView.vue      # Screen 2: Prediction + mechanism
│   │   │   └── EvidenceView.vue     # Screen 3: Expandable evidence
│   │   ├── stores/
│   │   │   └── explainability.js    # Pinia store (ExplainabilityResult)
│   │   ├── services/
│   │   │   ├── protox.js            # ProTox-II API calls (temporary)
│   │   │   ├── model.js             # Our model API calls (replace protox.js later)
│   │   │   └── llm.js               # LLM interpretability calls
│   │   ├── types/
│   │   │   └── dataClasses.js       # JSDoc definitions for all data classes
│   │   ├── App.vue
│   │   └── main.js
│   ├── public/
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
│
├── database/                        # STREAM 1 — Centralised toxicity database
│   ├── pipeline/
│   │   ├── ingest.py                # Raw data ingestion from public sources
│   │   ├── normalise.py             # Unify file types + variable names
│   │   └── export.py                # Export to unified format
│   ├── sources/
│   │   └── sources.md               # List of public databases used
│   ├── outputs/
│   │   └── .gitkeep                 # Processed data goes here (not committed)
│   └── README.md
│
├── model/                           # STREAM 2 — AI toxicity prediction models
│   ├── pretraining/
│   │   ├── semi_supervised.py       # Semi-supervised learning approach
│   │   └── contrastive.py           # Contrastive learning approach
│   ├── finetuning/
│   │   └── finetune.py              # Fine-tune on labelled toxicity data
│   ├── evaluation/
│   │   ├── scaffold_split.py        # Scaffold-based train/test splitting
│   │   └── metrics.py               # Accuracy, AUC, endpoint results
│   ├── checkpoints/
│   │   └── .gitkeep                 # Saved model weights (not committed)
│   ├── api/
│   │   └── serve.py                 # Serves predictions to the frontend
│   └── README.md
│
├── api/                             # Shared backend / data layer
│   ├── routes/
│   ├── data/
│   │   ├── mechanism_records.json   # Curated MechanismRecord data (Groups A/B)
│   │   └── evidence_items.json      # EvidenceItem data from Groups A/B
│   └── README.md
│
├── docs/
│   ├── schema.md                    # Agreed JSON schema for all data classes
│   ├── api-contract.md              # Prediction API format (ProTox now, our model later)
│   ├── git-workflow.md              # Branching + commit conventions
│   └── figma-link.md                # Link to Figma design file
│
├── .gitignore
└── README.md
```

## The three streams

| Stream | Folder | Status |
|---|---|---|
| 1 — Database | `/database` | ✅ Complete |
| 2 — Model | `/model` | 🔄 In progress (76% accuracy on test data) |
| 3 — Explainable UI | `/frontend` + `/api` | 🔄 In progress |

## Data classes

| Class | Source | Format |
|---|---|---|
| `QueryInput` | User | SMILES string |
| `ProToxPrediction` | ProTox-II API (temporary) | JSON |
| `MechanismRecord` | Groups A/B | JSON |
| `EvidenceItem` | Groups A/B | JSON |
| `InterpretabilityRule` | LLM | String |
| `MechanisticFlag` | Derived | JSON (organ targets) |
| `ExplainabilityResult` | Combined | JSON |

Full schemas → [`docs/schema.md`](docs/schema.md)
API contract → [`docs/api-contract.md`](docs/api-contract.md)

## Getting started

```bash
# Clone the repo
git clone https://github.com/melissaheine10-byte/toxexplain.git
cd toxexplain

# Frontend
cd frontend
npm install
npm run dev

# Model API (when ready)
cd model/api
pip install -r requirements.txt
python serve.py
```

## Branching convention

- `main` — stable, demo-ready only
- `dev` — integration branch, merge features here first
- `feature/your-name/what-youre-building` — your working branch

Stream branches for bigger parallel work:
- `stream/database`
- `stream/model`
- `stream/ui`


