# Original User Request

## Initial Request — 2026-07-25T22:11:18Z

# Teamwork Project Prompt — Draft

Criar uma estrutura robusta de documentação e revisão automatizada de código para o projeto TransfereGov API, assegurando o cumprimento dos padrões de qualidade definidos.

Working directory: /mnt/data/Projects_SSD/tranfere_gov_api
Integrity mode: development

## Requirements

### R1. Implementar ganchos locais e CI/CD para qualidade de código
Criar scripts automatizados (pre-commit hooks) e workflows de Integração Contínua (GitHub Actions) que validem todo novo código contra regras rigorosas (ruff e mypy), bloqueando commits ou PRs que contenham débitos técnicos ou não-conformidades.

### R2. Estruturar documentação do projeto
Criar/atualizar a documentação base do projeto (como `README.md` ou um diretório `docs/`) unificando as instruções de configuração do ambiente, execução local, e os processos automatizados de revisão de código, facilitando o onboarding de desenvolvedores.

## Acceptance Criteria

### Revisão de Código e Integração Contínua
- [ ] O arquivo `.pre-commit-config.yaml` existe e configura `ruff` (formatação e lint) e `mypy` (tipagem estrita).
- [ ] Um script em `.github/workflows/ci.yml` (ou similar) está configurado para testar PRs contra o ambiente Python.
- [ ] Rodar a verificação de código local de forma forçada valida os scripts e retorna sucesso (`pre-commit run --all-files`).

### Documentação
- [ ] A documentação central reflete as etapas exatas de instalação de dependências e configuração do pre-commit.
