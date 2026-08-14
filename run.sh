#!/usr/bin/env bash
# Atalhos para os scripts de extração Transferegov.
# Uso: ./run.sh <comando>
#
# Comandos:
#   discover       — Listar todos os objetos disponíveis para 2026
#   cemiterios     — Extrair todos os planos de cemitérios (objeto 301)
#   negados        — Extrair planos negados/perdidos de cemitérios
#   redator         — Redator oficial de documentos (nota-técnica, ofício, parecer)
#   all            — Extrair TODOS os objetos de 2026
#   help           — Mostrar esta ajuda

set -euo pipefail
cd "$(dirname "$0")"

# Ativar venv se existir
if [ -f ".venv/bin/activate" ]; then
    . .venv/bin/activate
fi

PYTHON="${PYTHON:-python3}"

usage() {
    cat <<EOF
Uso: $0 <comando> [opções]

Comandos:
  discover           Listar todos os objetos disponíveis para 2026
  cemiterios         Extrair cemitérios (objeto 301) — aceita args extras
  negados            Extrair negados/perdidos (objeto 301) — aceita args extras
  import             Importar JSONs para o banco PostgreSQL
  report             Relatórios do banco (resumo|estado|objeto|negados|emenda|top|sql)
  dashboard          Dashboard interativo HTML com gráficos Plotly
  web                Painel Web interativo do Deputado (FastAPI, porta 8001)
  enrich             Pipeline de enriquecimento (CNPJ + IBGE + Câmara)
  validate           Validar CNPJs via BrasilAPI
  ibge               Enriquecer municípios via IBGE
  camara             Perfil de parlamentares via Câmara
  governadores       Sincronizar governadores estaduais 2022 (TSE)
  votacoes           Votações e votos nominais da Câmara (por ano)
  cron-diario        Roda o worker do Diário Oficial (baixa DOU e gera resumo)
   qdrant-status      Status da indexação no Qdrant (vetores, deputados, cobertura)
   qdrant-staleness   Staleness do Qdrant — deputados desatualizados vs checkpoint
   localai-health     Saúde do LocalAI (API, modelos, VRAM, circuit breaker)
   cron-qdrant        Roda o Indexador do Qdrant para alimentar RAG
   rag-efficiency     Coletor de métricas RAG Efficiency (--politico-id)
   logit-lens-runner  Roda o Logit Lens offline para um run de efficiency (--run-id)
   vllm               Gerencia servidor vLLM local (start|stop|status|chat) — ver scripts/serve_vllm.sh
    vllm-bench         Benchmark comparativo vLLM vs LocalAI — ver scripts/benchmark_vllm_vs_localai.py
    logit-lens         Logit lens probe — eficiência do RAG v7 (--nome, --tipo, --pergunta)
   discursos          Extrai discursos da Câmara dos Deputados (--ano, --resumo)
  redator            Redator oficial de documentos (nota-técnica | ofício | parecer | despacho | validar)
  transparencia      Buscar emendas no Portal da Transparência (--nome-autor, --ano, --db, --csv, --json)
  dossie             Gerar dossiê RAG v8 (--nome, --tipo deputado|senador|governador|prefeito|vereador, --lote N)
  dossie-bench       Benchmark de dossiês (--golden | --tipo T --lote N | --nomes X --tipo T --saida F)
  all                Extrair TODOS os objetos de 2026
  help               Mostrar esta ajuda

Flags extras (passar após o comando):
  --db               Salvar no PostgreSQL
  --csv              Exportar CSV além de Excel
  --programa N       Filtrar por programaId (25 = Transferências Especiais)
  --uf UF            Filtrar por UF
  --situacao-api S   Filtrar por situação na API (ex: IMPEDIDO)
  -v                 Logging verboso

Exemplos:
  ./run.sh discover
  ./run.sh cemiterios --db --csv
  ./run.sh negados --db
  ./run.sh import
  ./run.sh report resumo
  ./run.sh report parlamentar
  ./run.sh report sql "SELECT ..."

Extração por programa + situação:
  python3 -m src.transferegov_extract --objeto all --ano 2026 --programa 25 --situacao-api IMPEDIDO --db --csv
EOF
}

case "${1:-help}" in
    discover)
        $PYTHON -m src.transferegov_extract --discover --ano 2026
        ;;
    cemiterios)
        $PYTHON -m src.transferegov_extract --objeto 301 --ano 2026 "${@:2}"
        ;;
    negados)
        $PYTHON -m src.transferegov_extract --objeto 301 --ano 2026 --negados "${@:2}"
        ;;
    import)
        $PYTHON -m src.db_import "${@:2}"
        ;;
    report)
        $PYTHON -m src.db_report "${@:2}"
        ;;
    dashboard)
        echo "📊 Iniciando Dashboard em http://localhost:8050 ..."
        $PYTHON -m src.dash_app "${@:2}"
        ;;

    dash)
        echo "📊 Iniciando Dashboard em http://localhost:8050 ..."
        $PYTHON -m src.dash_app "${@:2}"
        ;;
    web)
        echo "🌐 Iniciando Painel Web do Deputado em http://localhost:8001 ..."
        $PYTHON -m uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8001
        ;;
    enrich)
        $PYTHON -m src.enrichers.pipeline "${@:2}"
        ;;
    validate)
        $PYTHON -m src.enrichers.validacao "${@:2}"
        ;;
    ibge)
        $PYTHON -m src.enrichers.ibge "${@:2}"
        ;;
    camara)
        $PYTHON -m src.enrichers.camara "${@:2}"
        ;;
    votacoes)
        $PYTHON -m src.enrichers.votacoes_camara "${@:2}"
        ;;
    governadores)
        echo "🏛️ Sincronizando governadores estaduais (TSE 2022)..."
        $PYTHON -m src.enrichers.governadores "${@:2}"
        ;;
    qdrant-status)
        $PYTHON -m src.qdrant_status
        ;;
    qdrant-staleness)
        $PYTHON -m src.qdrant_staleness "${@:2}"
        ;;
    localai-health)
        $PYTHON -m src.localai_health "${@:2}"
        ;;
    cron-diario)
        $PYTHON -m src.enrichers.diario_oficial_worker "${@:2}"
        ;;
    cron-qdrant)
        $PYTHON -m src.enrichers.rag_qdrant_indexer "${@:2}"
        ;;
    cron-dossie)
        $PYTHON -m src.enrichers.rag_persona "${@:2}"
        ;;
    dossie)
        # Gera dossiê RAG v8 (multi-cargo). Ex.: ./run.sh dossie --nome "RENAN CALHEIROS" --tipo senador
        $PYTHON -m src.enrichers.rag_persona "${@:2}"
        ;;
    dossie-bench)
        # Benchmark de dossiês (multi-cargo, checkpoint, golden). Ex.:
        #   ./run.sh dossie-bench --golden
        #   ./run.sh dossie-bench --tipo senador --lote 5
        #   ./run.sh dossie-bench --nomes "ALFREDO GASPAR" --tipo deputado --saida reports/dossier_bench/run_x.jsonl
        $PYTHON scripts/dossier_bench.py "${@:2}"
        ;;
    discursos)
        $PYTHON -m src.enrichers.camara_discursos "${@:2}"
        ;;
    transparencia)
        $PYTHON -m src.extrator_transparencia "${@:2}"
        ;;
    vllm)
        $PYTHON -m src.local_vllm "${@:2}"
        ;;
    vllm-bench)
        $PYTHON -m scripts.benchmark_vllm_vs_localai "${@:2}"
        ;;
    redator)
        $PYTHON -m src.redator_transferegov "${@:2}"
        ;;
    rag-efficiency)
        $PYTHON -m src.enrichers.rag_efficiency_collector "${@:2}"
        ;;
    logit-lens-runner)
        $PYTHON -m scripts.logit_lens_runner "${@:2}"
        ;;
    logit-lens)
        $PYTHON -m src.logit_lens_probe "${@:2}"
        ;;
    all)
        $PYTHON -m src.transferegov_extract --objeto all --ano 2026 --csv "${@:2}"
        ;;
    help|--help|-h)
        usage
        ;;
    *)
        echo "Comando desconhecido: $1"
        echo ""
        usage
        exit 1
        ;;
esac
