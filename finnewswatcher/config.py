from pathlib import Path
from typing import Any, get_args, List, Literal, Optional
from yaml import safe_load
from pydantic import BaseModel, Field, model_validator, HttpUrl
from typing import Dict

from finnewswatcher.models import EventClass


# --- Bonuses Submodel ---
class Bonuses(BaseModel):
    numbers_present: int
    named_counterparty: int
    novel: int
    importance3: int
    first_party: int
    rumour_penalty: int


# --- Thresholds Model ---
class Thresholds(BaseModel):
    # --- Delivery & Schedule ---
    digest_time: str
    timezone: str
    digest_count_target: int = 7

    # --- Gates & Windows ---
    alert_threshold: int
    novelty_window_days: int
    dedupe_window_hours: int
    judge_min_score: int

    # --- LLM Runtime ---
    llm_temperature: float = 0.2
    timeout_seconds: int = 30

    # --- Scoring ---
    base_weights: Dict[str, int] = Field(default_factory=dict)
    bonuses: Bonuses

    @model_validator(mode="after")
    def check_keys(self) -> "Thresholds":
        # Validate base_weights keys against EventClass literal
        allowed_event_keys = set(get_args(EventClass))  # ('Earnings', 'Guidance', 'M&A', ...)
        provided_event_keys = set(self.base_weights.keys())

        missing = allowed_event_keys - provided_event_keys
        extra = provided_event_keys - allowed_event_keys

        errs = []
        if missing:
            errs.append(f"base_weights missing keys: {sorted(missing)}")
        if extra:
            errs.append(f"base_weights has unexpected keys: {sorted(extra)}")

        if not all(isinstance(v, int) for v in self.base_weights.values()):
            errs.append("base_weights values must be integers")

        if errs:
            raise ValueError("; ".join(errs))
        return self
    

# --- Sources Model ---
class SourceConfig(BaseModel):
    name: str
    type: Literal["rns", "press", "wire", "filing"]
    region: str
    url: HttpUrl
    enabled: bool = True
    fetch_limit: int = 20
    notes: Optional[str] = None


# --- Get root of file path ---
def _project_root() -> Path:
    """
    Find the repository root by searching upward for pyproject.toml.
    Falls back to the directory containing this file if not found.
    """
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    return current.parent


# --- Load yaml file ---
def load_yaml(path: Path) -> Any:
    """
    Load a YAML file (UTF-8) and return the parsed Python object.
    Raises clear errors for missing/empty/invalid files.
    """
    if not path.exists():
        raise FileNotFoundError(f"File does not exist: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = safe_load(f)

    if data is None:
        raise ValueError(f"Empty YAML: {path}")

    return data

# --- Load thresholds from configs/thresholds.yaml ---
def load_thresholds() -> Thresholds:
    cfg_path = _project_root() / "configs" / "thresholds.yaml"
    raw = load_yaml(cfg_path)
    if not isinstance(raw, dict):
        raise TypeError(f"thresholds.yaml must be a mapping at top level: {cfg_path}")
    return Thresholds(**raw)


# --- Load sources from configs/sources.yaml --- 
def load_sources() -> List[SourceConfig]:
    cfg_path = _project_root() / "configs" / "sources.yaml"
    data = load_yaml(cfg_path)

    if data is None:
        raise ValueError("sources.yaml is empty")

    if not isinstance(data, list):
        raise TypeError(f"Empty YAML: {cfg_path}")
    
    sources: list[SourceConfig] = []
    
    for item in data:
        if not isinstance(item, dict):
            raise TypeError(f"{item} is not a dict")
        sources.append(SourceConfig(**item))
    
    enabled_sources = [s for s in sources if s.enabled]
    
    return enabled_sources