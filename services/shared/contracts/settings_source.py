from pydantic import BaseModel, ConfigDict


class SettingsSourceRead(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    required_env_vars: frozenset[str]
    optional_env_vars: frozenset[str]
    secret_mounts: frozenset[str]

