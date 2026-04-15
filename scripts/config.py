import os
from pathlib import Path

# Try to load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    # Look for .env in project root (parent of scripts/)
    env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(dotenv_path=env_path)
except ImportError:
    # python-dotenv not installed, try manual parsing
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

# Load API key from environment variable or .env file
UPSTAGE_API_KEY = os.getenv("UPSTAGE_API_KEY")

# Embedding priority: local (BGE-m3-ko) first → Solar API fallback
LOCAL_EMBEDDING_MODEL = "dragonkue/BGE-m3-ko"

def _check_local_embedding_available():
    try:
        import sentence_transformers  # noqa: F401
        return True
    except ImportError:
        return False

LOCAL_EMBEDDING_AVAILABLE = _check_local_embedding_available()

if not LOCAL_EMBEDDING_AVAILABLE and not UPSTAGE_API_KEY:
    raise ValueError(
        "❌ 임베딩 모델을 사용할 수 없습니다.\n"
        "   옵션 1: pip install sentence-transformers (로컬 모델)\n"
        "   옵션 2: .env에 UPSTAGE_API_KEY 설정 (Solar API)"
    )

UPSTAGE_BASE_URL = "https://api.upstage.ai/v1"

# Claude API - used for tagging and dialog classification
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"

EMBEDDING_MODEL = "embedding-passage"
LLM_MODEL = "solar-mini"

TEXT_STRATEGY_MIN_SUMMARY_LENGTH = 50
TEXT_STRATEGY_MIN_FIRST_MSG_LENGTH = 20
TEXT_STRATEGY_TURNS_COUNT = 6

DEFAULT_K_RANGE = [8, 10, 12, 15, 20, 25]
DEFAULT_CACHE_DIR = "cache"
DEFAULT_OUTPUT_DIR = "results"
DEFAULT_OUTPUT_PREFIX = "output"

LLM_TEMPERATURE = 0.3
LLM_SAMPLES_PER_CLUSTER = 20
EMBEDDING_BATCH_SIZE = 100
