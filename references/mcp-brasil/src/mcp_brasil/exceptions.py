"""Exceções do projeto mcp-brasil."""


class McpBrasilError(Exception):
    """Exceção base para todas as exceções do mcp-brasil."""


class FeatureError(McpBrasilError):
    """Erro relacionado a uma feature (discovery, validação, etc.)."""


class HttpClientError(McpBrasilError):
    """Erro de comunicação HTTP com API externa."""


class AuthError(McpBrasilError):
    """Credencial ausente ou inválida para acessar API protegida."""
