# API contract

This document defines how the frontend receives toxicity predictions. The frontend is built to be model-agnostic — swapping the prediction source requires only changing the service file, not the UI components.

---

## Current setup (ProTox-II)

The frontend calls `frontend/src/services/protox.js`, which queries the ProTox-II web server.

**Input:**
```json
{ "smiles": "CC(=O)Oc1ccccc1C(=O)O" }
```

**Output** (normalised into our schema):
```json
{
  "smiles": "CC(=O)Oc1ccccc1C(=O)O",
  "ld50": 200,
  "toxicity_class": 3,
  "toxicity_class_label": "Toxic",
  "endpoints": {
    "hepatotoxicity": true,
    "nephrotoxicity": false,
    "immunotoxicity": false,
    "mutagenicity": false,
    "cytotoxicity": true
  }
}
```

---

## Future setup (our model)

When the model API is ready (`model/api/serve.py`), swap `protox.js` for `model.js` in the frontend. The output format is identical — no UI changes needed.

**Model API endpoint:**
```
POST http://localhost:8000/predict
Body: { "smiles": "..." }
```

The response must match the schema above exactly so the frontend components work without modification.

---

## Integration checklist

- [ ] ProTox-II integration working in frontend
- [ ] `model/api/serve.py` returning predictions in correct format
- [ ] `frontend/src/services/model.js` written and tested
- [ ] Switch `protox.js` → `model.js` in `App.vue` or router
- [ ] End-to-end test: SMILES in → ExplainabilityResult out
