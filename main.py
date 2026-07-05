from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import os
import yaml
from dotenv import dotenv_values

app = FastAPI()

# CORS: lets a webpage (like the grader's checker page) call this API
# from a different domain. Without this, browsers block the request.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Layer 1: defaults, always the starting point
DEFAULTS = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000",
}

# Maps "weird" file key names to our clean internal names
ALIASES = {
    "NUM_WORKERS": "workers",
    "APP_PORT": "port",
    "APP_WORKERS": "workers",
    "APP_DEBUG": "debug",
    "APP_LOG_LEVEL": "log_level",
    "APP_API_KEY": "api_key",
}


def load_yaml_layer():
    """Layer 2: config.development.yaml"""
    try:
        with open("config.development.yaml") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}


def load_dotenv_layer():
    """Layer 3: .env file (read WITHOUT touching real OS env vars)"""
    raw_values = dotenv_values(".env")
    layer = {}
    for key, value in raw_values.items():
        clean_key = ALIASES.get(key, key.lower())
        layer[clean_key] = value
    return layer


def load_os_env_layer():
    """Layer 4: real OS environment variables, only ones starting with APP_"""
    layer = {}
    for key, value in os.environ.items():
        if key in ALIASES:
            layer[ALIASES[key]] = value
        elif key.startswith("APP_"):
            layer[key[len("APP_"):].lower()] = value
    return layer


def coerce(key, value):
    """Turns raw strings into the correct type for each key."""
    if key in ("port", "workers"):
        return int(value)
    if key == "debug":
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("true", "1", "yes", "on")
    return str(value)


@app.get("/effective-config")
def effective_config(request: Request):
    # Start with defaults, then let each later layer overwrite matching keys
    merged = dict(DEFAULTS)
    for layer in (load_yaml_layer(), load_dotenv_layer(), load_os_env_layer()):
        merged.update(layer)

    # Layer 5: CLI overrides, e.g. ?set=port=9000&set=debug=true
    for raw in request.query_params.getlist("set"):
        if "=" in raw:
            k, v = raw.split("=", 1)
            merged[k.strip()] = v.strip()

    # Build the final response with correct types
    response = {
        "port": coerce("port", merged.get("port", DEFAULTS["port"])),
        "workers": coerce("workers", merged.get("workers", DEFAULTS["workers"])),
        "debug": coerce("debug", merged.get("debug", DEFAULTS["debug"])),
        "log_level": coerce("log_level", merged.get("log_level", DEFAULTS["log_level"])),
        "api_key": "****",  # NEVER return the real key
    }
    return response