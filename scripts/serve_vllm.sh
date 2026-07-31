#!/usr/bin/env bash
# ------------------------------------------------------------------
# serve_vllm.sh — Sobe servidor vLLM local com modelo GGUF
# ------------------------------------------------------------------
# Uso:
#   ./scripts/serve_vllm.sh                              # menu interativo
#   ./scripts/serve_vllm.sh llama-3.2-3b                  # modelo pelo nome lógico
#   ./scripts/serve_vllm.sh --model path/to/model.gguf    # path direto
#   ./scripts/serve_vllm.sh --list                        # lista modelos disponíveis
#
# Dependências: vllm instalado no .venv do fork (ou via pip)
# GPU: NVIDIA com CUDA 12+ recomendado
# ------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VLLM_FORK_DIR="${LOCAL_VLLM_FORK_DIR:-$PROJECT_ROOT/../vllm}"
MODELS_DIR="${LOCAL_VLLM_MODELS_DIR:-/mnt/data/models}"
BASE_URL="${LOCAL_VLLM_BASE_URL:-http://localhost:8001}"
PORT="${LOCAL_VLLM_PORT:-8001}"
GPU_MEM="${LOCAL_VLLM_GPU_MEM_UTIL:-0.88}"
MAX_LEN="${LOCAL_VLLM_MAX_MODEL_LEN:-8192}"

# Ativar venv do projeto (fallback: tenta o fork)
if [ -f "$PROJECT_ROOT/.venv/bin/activate" ]; then
    source "$PROJECT_ROOT/.venv/bin/activate"
elif [ -f "$VLLM_FORK_DIR/.venv/bin/activate" ]; then
    source "$VLLM_FORK_DIR/.venv/bin/activate"
fi

# Cores para output
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

# ------------------------------------------------------------------
# Mapa de modelos lógicos → paths GGUF + tokenizer
# ------------------------------------------------------------------
declare -A MODEL_MAP
MODEL_MAP["llama-3.2-3b"]="$MODELS_DIR/localai/llm/llama-3.2-3b/llama-3.2-3b-instruct-q4_k_m.gguf|hugging-quants/Llama-3.2-3B-Instruct-GGUF"
MODEL_MAP["llama-3.2-3b-q8"]="$MODELS_DIR/localai/llm/llama-3.2-3b/llama-3.2-3b-instruct-q8_0.gguf|hugging-quants/Llama-3.2-3B-Instruct-GGUF"
MODEL_MAP["gemma-4-e2b"]="$MODELS_DIR/localai/llm/gemma-4/gemma-4-E2B-it-Q8_0.gguf|google/gemma-4-e2b-it"
MODEL_MAP["qwen2.5-1.5b"]="$MODELS_DIR/localai/llm/qwen2.5-1.5b/qwen2.5-1.5b-instruct-q4_k_m.gguf|Qwen/Qwen2.5-1.5B-Instruct"
MODEL_MAP["qwen2.5-coder-7b"]="$MODELS_DIR/lmstudio-community/Qwen2.5-Coder-7B-Instruct-GGUF/Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf|Qwen/Qwen2.5-Coder-7B-Instruct"
MODEL_MAP["gemma-4-12b"]="$MODELS_DIR/lmstudio-community/gemma-4-12B-it-QAT-GGUF/gemma-4-12B-it-QAT-Q4_0.gguf|google/gemma-4-12b-it-QAT"
MODEL_MAP["minicpm4-8b"]="$MODELS_DIR/QuantFactory/MiniCPM4-8B-GGUF/MiniCPM4-8B.Q4_K_M.gguf|openbmb/MiniCPM4-8B"

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
list_models() {
    echo -e "${CYAN}Modelos GGUF disponíveis:${NC}"
    for key in "${!MODEL_MAP[@]}"; do
        IFS='|' read -r path tokenizer <<< "${MODEL_MAP[$key]}"
        if [ -f "$path" ]; then
            size=$(du -h "$path" | cut -f1)
            echo -e "  ${GREEN}✓${NC} $key  (${size})"
        else
            echo -e "  ${RED}✗${NC} $key  (arquivo não encontrado)"
        fi
    done
}

choose_model() {
    echo -e "${CYAN}Selecione um modelo para servir:${NC}"
    local i=1
    local keys=()
    for key in "${!MODEL_MAP[@]}"; do
        IFS='|' read -r path tokenizer <<< "${MODEL_MAP[$key]}"
        if [ -f "$path" ]; then
            size=$(du -h "$path" | cut -f1)
            echo -e "  ${GREEN}$i)${NC} $key  (${size})"
            keys+=("$key")
            ((i++))
        fi
    done
    echo ""
    read -rp "Escolha (1-$((i-1))): " choice
    if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -lt "$i" ]; then
        echo "${keys[$((choice-1))]}"
    else
        echo ""
    fi
}

get_model_info() {
    local name="$1"
    if [[ -f "$name" ]]; then
        # É path direto
        MODEL_PATH="$name"
        TOKENIZER="${2:-auto}"
        return 0
    fi
    if [[ -v MODEL_MAP[$name] ]]; then
        IFS='|' read -r MODEL_PATH TOKENIZER <<< "${MODEL_MAP[$name]}"
        if [ ! -f "$MODEL_PATH" ]; then
            echo -e "${RED}Arquivo não encontrado: $MODEL_PATH${NC}" >&2
            return 1
        fi
        return 0
    fi
    echo -e "${RED}Modelo desconhecido: $name${NC}" >&2
    echo -e "Use --list para ver os disponíveis." >&2
    return 1
}

# ------------------------------------------------------------------
# Servir modelo
# ------------------------------------------------------------------
serve_model() {
    local model_path="$1"
    local tokenizer="$2"

    echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  Iniciando vLLM server local                           ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "  Modelo:      $model_path"
    echo "  Tokenizer:   $tokenizer"
    echo "  Porta:       $PORT"
    echo "  GPU mem:     ${GPU_MEM}"
    echo "  Max tokens:  ${MAX_LEN}"
    echo "  API:         ${BASE_URL}/v1"
    echo ""

    # Verifica se já tem algo na porta
    if ss -tlnp | grep -q ":$PORT "; then
        echo -e "${YELLOW}Aviso: porta $PORT já está em uso.${NC}"
        echo -e "${YELLOW}Pare o processo atual ou mude LOCAL_VLLM_PORT${NC}"
        read -rp "Continuar mesmo assim? (s/N) " confirm
        if [[ ! "$confirm" =~ ^[sS]$ ]]; then
            echo "Abortando."
            exit 1
        fi
    fi

    # Verifica se vLLM está instalado
    if ! python -c "import vllm" 2>/dev/null; then
        echo -e "${RED}vLLM não encontrado no Python atual.${NC}"
        echo -e "Instale via: pip install vllm"
        echo -e "Ou do fork:  cd $VLLM_FORK_DIR && pip install -e ."
        exit 1
    fi

    echo -e "${YELLOW}Pressione Ctrl+C para parar o servidor.${NC}"
    echo ""

    python -m vllm.entrypoints.openai.api_server \
        --model "$model_path" \
        --tokenizer "$tokenizer" \
        --host "0.0.0.0" \
        --port "$PORT" \
        --gpu-memory-utilization "$GPU_MEM" \
        --max-model-len "$MAX_LEN" \
        --served-model-name "$(basename "$model_path" .gguf)" \
        --api-key "not-set" \
        --enable-prefix-caching
}

# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------
case "${1:-}" in
    --list|-l)
        list_models
        exit 0
        ;;
    --help|-h)
        echo "Uso: $0 [model_name|--list|--help]"
        echo ""
        echo "  model_name    Serve modelo pelo nome lógico (ex: llama-3.2-3b)"
        echo "  --model PATH  Serve modelo por path direto ao .gguf"
        echo "  --list        Lista modelos disponíveis"
        echo "  --help        Esta ajuda"
        exit 0
        ;;
    --model)
        if [ $# -lt 2 ]; then
            echo -e "${RED}Erro: --model requer path do .gguf${NC}" >&2
            exit 1
        fi
        shift
        MODEL_PATH="$1"
        TOKENIZER="${2:-auto}"
        ;;
    "")
        # Modo interativo
        selected=$(choose_model)
        if [ -z "$selected" ]; then
            echo "Nenhum modelo selecionado."
            exit 1
        fi
        get_model_info "$selected" || exit 1
        ;;
    *)
        get_model_info "$1" || exit 1
        ;;
esac

serve_model "$MODEL_PATH" "$TOKENIZER"
