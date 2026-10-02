"""ByteLens core library.

Explanation-aware robustness of image-based malware classifiers: PE-valid
problem-space attacks on predictions and Grad-CAM explanations, and an
Explanation-Consistency Training (ECT) defense.

Domain modules (AGENTS.md section 4):

- ``bytelens.render``   binary -> image, shared differentiable resize (ADR-002)
- ``bytelens.regions``  canonical flag-based PE partition (ADR-001)
- ``bytelens.models``   cnn, resnet, malconv, lightgbm features
- ``bytelens.explain``  grad-cam, integrated gradients, score-cam, faithfulness,
                        collapse guard
- ``bytelens.attacks``  PE editors (append / inject-section / pad-slack), A1-A8
- ``bytelens.defenses`` canonicalization, adversarial training, ECT, ECT-A
- ``bytelens.eval``     splits, AUT, open-set, stats, audits

Modules fill in per the phase plan (P0 scaffold -> P1 data/baselines ->
P2 audits -> P3 attacks/defenses). Modules raise ``NotImplementedError``
until their phase; no placeholder numbers anywhere.
"""

__version__ = "0.1.0"
