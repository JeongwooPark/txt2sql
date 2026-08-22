# Korean PostGIS NL2SQL benchmark (v1)

Gold is `gold Plan + result hash + clarify`. Execution success is not accuracy.

| file | role | status |
|---|---|---|
| `train.jsonl` | training / few-shot pool | filled from STEP-02 |
| `dev.jsonl` | development | filled from STEP-02 |
| `test.jsonl` | official verified eval | filled from STEP-02 |
| `adversarial.jsonl` | paraphrase / trap cases | STEP-02+ |
| `conversation.jsonl` | multi-turn | Phase 4 |
| `candidate_compound30.jsonl` | imported smoke 30 | **draft only** |
| `candidate_nl100.jsonl` | imported smoke 100 | **draft only** |

Rules:

- Do not copy current system Plan/SQL into gold.
- Official metrics use `status=verified` only.
- `candidate_*` files keep `status=draft`.
