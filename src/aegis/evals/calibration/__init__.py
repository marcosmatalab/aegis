"""F5 judge calibration: measure AGREEMENT between hand labels and the real
judge with Cohen's kappa (per criterion + global), never ground truth.

The judge stays DIRECTIONAL — see the README for the honesty caveats: N=30 gives
a wide CI, kappa is base-rate sensitive (the kappa paradox) so p_o + the matrix
are reported beside it, a single annotator applied the rubric (not consensus
gold), parse failures are excluded and counted, and the Landis-Koch bands are
arbitrary conventions.
"""

from aegis.evals.calibration.dataset import (
    DEFAULT_CALIBRATION_PATH,
    CalibrationDatasetError,
    load_calibration,
)
from aegis.evals.calibration.kappa import (
    ConfusionMatrix,
    KappaResult,
    binarize,
    build_matrix,
    cohen_kappa,
    kappa_from_pairs,
    landis_koch_band,
)
from aegis.evals.calibration.models import CalibrationCase
from aegis.evals.calibration.report import (
    CalibrationReport,
    KappaSection,
    compute_calibration,
)
from aegis.evals.calibration.runner import run_calibration

__all__ = [
    "DEFAULT_CALIBRATION_PATH",
    "CalibrationCase",
    "CalibrationDatasetError",
    "CalibrationReport",
    "ConfusionMatrix",
    "KappaResult",
    "KappaSection",
    "binarize",
    "build_matrix",
    "cohen_kappa",
    "compute_calibration",
    "kappa_from_pairs",
    "landis_koch_band",
    "load_calibration",
    "run_calibration",
]
