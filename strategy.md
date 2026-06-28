# Data Handling Strategy for Brazilian Government API Integration

## 1. Data Storage & Processing
*   **Database Selection**: Use a robust relational database (e.g., PostgreSQL via Cloud SQL) for structured integration data (proposals, goals, subgoals). This provides ACID compliance, critical for financial/government data. Use NoSQL (e.g., Firestore or MongoDB) for flexible, unstructured payload logging and audit trails.
*   **Data Minimization**: Only retrieve and store the exact data points required for the business process. Do not store massive unindexed JSON blobs if only specific fields are needed.
*   **Processing Pipeline**: Implement an asynchronous processing queue (e.g., RabbitMQ, Google Cloud Tasks, or AWS SQS) to handle API rate limits, transient network failures, and retries with exponential backoff when fetching or pushing data to government systems.

## 2. Security Best Practices
*   **Encryption**: All data must be encrypted at rest (AES-256) and in transit (TLS 1.3).
*   **Secret Management**: Never hardcode API keys, CPF credentials, or tokens. Use a secure vault like Google Secret Manager, AWS Secrets Manager, or HashiCorp Vault.
*   **Token Lifecycle**: Implement automated token rotation. Government IDP tokens and system-level JWTs (like EP-CAD) often have short TTLs. Maintain a secure token cache that preemptively refreshes tokens before they expire.

## 3. Compliance with LGPD (Lei Geral de Proteção de Dados)
*   **Consent and Legal Basis**: Ensure that if personal data (e.g., CPFs of public servants or engineers) is processed, it is done under a valid legal basis (such as compliance with a legal obligation or execution of a public policy).
*   **Anonymization & Auditing**: Maintain strict audit logs of who accessed what data and when. Implement data masking for sensitive fields in UI dashboards.
*   **Data Subject Rights**: Provide mechanisms for users to request data deletion or access, specifically for non-public data (though public procurement data is generally public domain under the Transparency Law).

## 4. Known Issues & Best Programming Language
*   **Known Issues**: 
    *   **Rate Limiting & Instability**: Government APIs (like Transferegov or Receita Federal) frequently experience downtime or slow response times during peak hours (e.g., end of month/year reporting).
    *   **Inconsistent Documentation**: Swagger files or documentation may lag behind actual API implementations. Sandbox/Homologation environments are often broken or out of sync with production.
    *   **Complex Auth Flows**: Combining machine-to-machine JWTs with user-delegated IDP tokens can be fragile.
*   **Best Programming Language**: **TypeScript (Node.js)** is highly recommended. It offers excellent ecosystem support for JWT manipulation, asynchronous queuing, and robust typing to model complex government payloads safely. Go (Golang) is also a strong contender for highly concurrent, CLI-based agents due to its fast compilation and memory safety.

## 5. Key Brazilian Government APIs for Data Retrieval
1.  **Transferegov.br (formerly Plataforma +Brasil)**
    *   **Purpose**: Management of federal resource transfers, agreements, and public contracts.
    *   **Data Provided**: Proposals, work plans, budget worksheets (PLE/BM), physical-financial execution, and bidding processes.
    *   **Integration**: Uses RESTful architecture. Requires a dual-token system (System Token + User Auth Token).
2.  **Receita Federal (CNPJ API/Serpro)**
    *   **Purpose**: Corporate entity validation.
    *   **Data Provided**: Company registration details, tax status, CNAE (economic activity codes), and ownership structures.
    *   **Integration**: Usually requires a paid contract via Serpro. Uses OAuth 2.0 or mutual TLS (mTLS).
3.  **Portal da Transparência API (CGU)**
    *   **Purpose**: Open data access to federal spending.
    *   **Data Provided**: Federal budget execution, public servant salaries, travel expenses, and federal contracts.
    *   **Integration**: API Key based. Free to use but strictly rate-limited.
4.  **IBGE APIs (e.g., API de Localidades)**
    *   **Purpose**: Geographic and demographic standard data.
    *   **Data Provided**: States, municipalities, micro-regions, and census data.
    *   **Integration**: Open/public REST API, no authentication required for standard geographic data. Useful for standardizing addresses and regions.

## 6. Authentication Methods
*   **API Key-Based Authentication**: Used primarily by open data portals (like Portal da Transparência).
    *   *Implementation*: Generate an API key in the provider's developer portal. Pass the key in the HTTP header (e.g., `chave-api-dados: YOUR_KEY`). Ensure the key is stored in a Secret Manager and never exposed to the client-side.
*   **OAuth 2.0 & Gov.br Login**: Required for APIs that access specific user or entity data (like Receita Federal or advanced Transferegov endpoints).
    *   *Implementation*: The system redirects the user to the `gov.br` login portal. Upon successful login, the provider returns an authorization code. The backend exchanges this code for an Access Token and a Refresh Token.
    *   *System-to-System (M2M)*: For background tasks, implement OAuth 2.0 Client Credentials Grant or signed JWT assertions (similar to the EP-CAD flow in Transferegov) where a private key is used to sign a token that the government API verifies.
