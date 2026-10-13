"""Models under test, with each vendor's recommended non-thinking sampling.

Thinking is disabled for every hybrid model: replies must be immediate and
short, and earlier screens showed thinking mode exhausting the token budget.
"""

NO_THINK = {"enable_thinking": False}

MODELS = {
    "minicpm5-1b": {
        "file": "MiniCPM5-1B-Q4_K_M.gguf",
        "repo": "openbmb/MiniCPM5-1B-GGUF",
        "sampling": {"temperature": 0.7, "top_p": 0.95},
        "template_kwargs": NO_THINK,
    },
    "gemma3-1b": {
        "file": "gemma-3-1b-it-Q4_K_M.gguf",
        "repo": "ggml-org/gemma-3-1b-it-GGUF",
        "sampling": {"temperature": 1.0, "top_k": 64, "top_p": 0.95},
    },
    "qwen3-1.7b": {
        "file": "Qwen3-1.7B-Q4_K_M.gguf",
        "repo": "unsloth/Qwen3-1.7B-GGUF",
        "sampling": {"temperature": 0.7, "top_p": 0.8, "top_k": 20, "min_p": 0.0},
        "template_kwargs": NO_THINK,
    },
    "minicpm5-2b": {
        "file": "MiniCPM5-2B-Q4_K_M.gguf",
        "repo": "openbmb/MiniCPM5-2B-GGUF",
        "sampling": {"temperature": 1.0, "top_p": 0.95, "min_p": 0.0},
        "template_kwargs": NO_THINK,
    },
    "gemma4-e2b": {
        "file": "gemma-4-E2B-it-Q4_K_M.gguf",
        "repo": "unsloth/gemma-4-E2B-it-GGUF",
        "sampling": {"temperature": 1.0, "top_k": 64, "top_p": 0.95},
        "template_kwargs": NO_THINK,
    },
    "llama3.2-3b": {
        "file": "Llama-3.2-3B-Instruct-Q4_K_M.gguf",
        "repo": "bartowski/Llama-3.2-3B-Instruct-GGUF",
        "sampling": {"temperature": 0.6, "top_p": 0.9},
    },
    "ministral3-3b": {
        "file": "Ministral-3-3B-Instruct-2512-Q4_K_M.gguf",
        "repo": "mistralai/Ministral-3-3B-Instruct-2512-GGUF",
        "sampling": {"temperature": 0.15},
    },
    "qwen3-4b-2507": {
        "file": "Qwen3-4B-Instruct-2507-Q4_K_M.gguf",
        "repo": "unsloth/Qwen3-4B-Instruct-2507-GGUF",
        "sampling": {"temperature": 0.7, "top_p": 0.8, "top_k": 20, "min_p": 0.0},
    },
}
