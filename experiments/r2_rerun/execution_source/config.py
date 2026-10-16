"""Central configuration for ARA (loaded from environment / .env)."""
import os
from dotenv import load_dotenv

load_dotenv()

# --- API keys ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")

# --- Models ---
LLM_MODEL = os.getenv("ARA_LLM_MODEL", "gpt-5-mini")          # generator (3C.1)
EMBED_MODEL = os.getenv("ARA_EMBED_MODEL", "text-embedding-3-small")  # 3C.5
OCR_MODEL = os.getenv("ARA_OCR_MODEL", "mistral-ocr-latest")  # 3C.9

# --- Baseline models for evaluation (general-purpose, no retrieval; Section 4.1) ---
MISTRAL_CHAT_MODEL = os.getenv("ARA_MISTRAL_CHAT_MODEL", "mistral-large-latest")
BASELINE_GPT_MODEL = os.getenv("ARA_BASELINE_GPT_MODEL", "gpt-5.2")

# --- Paths ---
# --- Serving corpus: the FULL knowledge base used to ANSWER queries (Source A+C+D...) ---
CORPUS_DIR = os.getenv("ARA_CORPUS_DIR", "./corpus")
DB_DIR = os.getenv("ARA_DB_DIR", "./vectordb")
STATS_PATH = os.getenv("ARA_STATS_PATH", os.path.join(DB_DIR, "corpus_stats.json"))

# --- Calibration corpus: SOURCE A ONLY, frozen. Binds the complexity model. ---
# The complexity scorer's ambiguity feature (idf stats + clarity index) always reads
# THIS calibration KB, so adding more contracts to the serving corpus does not change
# C(Q) or shift the calibrated threshold tau.
CALIB_CORPUS_DIR = os.getenv("ARA_CALIB_CORPUS_DIR", "./corpus_calibration")
CALIB_DB_DIR = os.getenv("ARA_CALIB_DB_DIR", "./calib_db")
CALIB_STATS_PATH = os.getenv("ARA_CALIB_STATS_PATH", os.path.join(CALIB_DB_DIR, "corpus_stats.json"))
COLLECTION = "construction_contracts"
LEARNED_WEIGHTS_PATH = os.getenv("ARA_LEARNED_WEIGHTS", "./calibration/learned_weights.json")

# --- Ambiguity feature mode (Caliberation.pdf Eq. 3 vs semantic clarity) ---
# 'idf'     : mean -log p(t|D)  (paper formula; does not separate on this data)
# 'clarity' : retrieval-dispersion entropy (semantic; needs vector DB + API)
AMB_MODE = os.getenv("ARA_AMB_MODE", "idf")
AMB_CLARITY_K = int(os.getenv("ARA_AMB_CLARITY_K", "8"))

# --- KB-sufficiency label thresholds (Caliberation.pdf 1.1) ---
COVERAGE_MIN = float(os.getenv("ARA_COVERAGE_MIN", "0.6"))        # rho_min
CONTRADICTION_MAX = float(os.getenv("ARA_CONTRADICTION_MAX", "0.2"))  # kappa_max

# --- Retrieval ---
TOP_K = int(os.getenv("ARA_TOP_K", "5"))
CHUNK_SIZE = int(os.getenv("ARA_CHUNK_SIZE", "900"))      # approx chars per chunk
CHUNK_OVERLAP = int(os.getenv("ARA_CHUNK_OVERLAP", "150"))

# --- RAG-Gym agentic loop ---
GYM_MAX_STEPS = int(os.getenv("ARA_GYM_MAX_STEPS", "6"))
GYM_NUM_CANDIDATES = int(os.getenv("ARA_GYM_NUM_CANDIDATES", "3"))  # Action 1|2|3 in Fig 1 (3B.2)

API_TIMEOUT = float(os.getenv("ARA_API_TIMEOUT", "120"))
