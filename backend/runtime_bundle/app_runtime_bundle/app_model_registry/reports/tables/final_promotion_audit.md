# Final Promotion Audit (Top 3 Candidates)

| Candidate | Flow AUC | PR-AUC | Session AUC | Block@FPR0 | Balanced R/FPR | Strict R/FPR | Calibration(best) | LODO |
|---|---:|---:|---:|---:|---|---|---|---|
| `diverse_bagging_robust9` | 0.9912 | 0.9646 | 0.9900 | 0.4545 | 0.9091/0.0196 | 0.7727/0.0000 | raw (ECE=0.0071) | n/a |
| `3dataset_REFRESH` | 0.9825 | 0.8513 | 0.9218 | 0.4000 | 0.4000/0.0000 | 0.2000/0.0000 | isotonic (ECE=0.0273) | isotonic holdout AUC min/mean/max=0.365/0.435/0.476 |
| `current_default` | 0.9825 | 0.8513 | 0.9218 | 0.4000 | 0.4000/0.0000 | 0.2000/0.0000 | isotonic (ECE=0.0273) | isotonic holdout AUC min/mean/max=0.365/0.435/0.476 |
