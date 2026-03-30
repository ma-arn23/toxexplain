# Git setup & workflow

## First-time setup (do this once)

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/toxexplain.git
cd toxexplain

# 2. Set your name and email (if you haven't before)
git config --global user.name "Your Name"
git config --global user.email "you@example.com"

# 3. Install frontend dependencies
cd frontend
npm install
```

---

## Daily workflow

```bash
# Always start by pulling the latest changes
git checkout dev
git pull origin dev

# Create your feature branch
git checkout -b feature/yourname/what-youre-building
# Example: git checkout -b feature/alice/prediction-summary-card

# ... do your work ...

# Stage and commit your changes
git add .
git commit -m "feat: add PredictionSummaryCard component"

# Push your branch
git push origin feature/yourname/what-youre-building

# Then open a Pull Request on GitHub into dev
```

---

## Commit message convention

Use these prefixes so everyone knows what changed at a glance:

| Prefix | When to use |
|---|---|
| `feat:` | New component or feature |
| `fix:` | Bug fix |
| `data:` | Adding or updating JSON data files |
| `docs:` | README, schema, or docs changes |
| `style:` | CSS / visual only changes |
| `refactor:` | Code restructure, no new features |

---

## Branch rules

- **Never commit directly to `main`**
- **Never commit directly to `dev`**
- Always make a feature branch → open a PR → get one teammate to review → merge into `dev`
- `main` is only updated when `dev` is stable and demo-ready

---

## Useful commands

```bash
# See what branch you're on and what's changed
git status

# See recent commit history
git log --oneline -10

# Grab latest changes without switching branches
git fetch origin

# Merge latest dev into your feature branch (do this often)
git merge origin/dev

# Undo unstaged changes to a file
git checkout -- filename.vue

# See what's different from last commit
git diff
```

---

## Adding the data files (Groups A/B)

Put your curated JSON in `api/data/`:
- `mechanism_records.json` — array of MechanismRecord objects
- `evidence_items.json` — array of EvidenceItem objects

Follow the schema in `docs/schema.md` exactly.
