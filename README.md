# Transferegov Developer Hub & API Simulator

## Overview
This repository contains a professional development portal and interactive simulator designed to assist Brazilian private systems in integrating with the **Transferegov.br** API. It focuses specifically on the "Projeto Básico" module, facilitating the construction, validation, and submission of Budget Worksheets (Planilha Orçamentária - PO) in both PLE and BM formats.

## Architecture & Technology Stack
- **Frontend**: React 18+ (Vite), TypeScript, Tailwind CSS, Lucide React (Icons), Framer Motion (Animations).
- **Backend/Middleware**: Express server serving as a Vite middleware proxy during development (`server.ts`). This allows local simulation of complex Transferegov endpoints (Authentication, Data Insertion, CSV Exports) without dealing with real-world instability.
- **Cloud Integration**: Firebase Authentication & Google Drive API (OAuth 2.0) are integrated to allow developers to securely save and load complex JSON payload states directly from their Google Drive.

## Key Features

### 1. Payload Generator (PLE & BM)
- A dynamic, heavily-typed GUI capable of visually assembling complex nested JSON hierarchies (Macroservices -> Services -> Events/Parcels).
- Distinct validation layers: 
  - **PLE format**: Relies on `evento` bindings.
  - **BM format**: Relies on `parcelas` bindings.
- **Client-Side Validation**: Automatically alerts users if a BM service's total percentages exceed 100%.

### 2. Sandbox API Tester (Local Simulator)
Provides a fully simulated integration environment mimicking the real Transferegov API:
- **`POST /login`**: Simulates the gov.br IDP (Identity Provider) authentication for public servants/engineers, returning an IDP JWT (`userToken`).
- **`GET /submetas`**: Simulates fetching the list of valid subgoals for a project and exposes the vital `indReceberPO_CFFviaAPI` flag.
- **`GET /consultar_proposta`**: Simulates an open data query that returns a CSV list of proposals mapped to a Politician's ID (Autor da Emenda).
- **`POST /po`**: Simulates pushing a finalized budget worksheet to the `hom4` or `prod` environments requiring dual-auth (EP-CAD system JWT + User Bearer IDP JWT).

### 3. AI Advisor (Integration Expert)
- A simulated intelligent agent embedded in the application that answers specific, contextual questions based on the Transferegov v1.3 API Integration Manual.

## Setup & Running Locally

1. **Install Dependencies:**
   ```bash
   npm install
   ```
2. **Setup Environment Variables:**
   Create a `.env` file referencing `.env.example` if available. Ensure your `firebase-applet-config.json` is properly populated for Drive integrations.
3. **Start the Development Server (Full-Stack Mode):**
   ```bash
   npm run dev
   ```
4. **Build for Production:**
   ```bash
   npm run build
   ```
   *Note: This utilizes `esbuild` to compile `server.ts` into a CommonJS server script (`dist/server.cjs`) to bypass strict node ESM rules, alongside the standard Vite static build.*

## Agent Context & Handoff Notes
*For autonomous agents working on this repo:*
- **Styling**: Always use Tailwind CSS (`className`) directly. Do not use external CSS files.
- **Icons**: Exclusively use `lucide-react`.
- **Database/Storage**: Complex relational mappings should prefer PostgreSQL/Cloud SQL if expanded. Document payload persistence is currently handled gracefully via Google Drive integration (`src/lib/drive.ts`).
- **Data Validation Strategy**: The app requires robust frontend schemas. Refer to the validation layer inside the `App.tsx` file to see how `BM` payload rules (e.g. `percentualParcela` max 100%) are actively checked via a reactive toast system. 
- **Simulators**: If expanding the API, add the mocked endpoints inside `server.ts` first so the client can reliably fetch against `/api/simulate/...`.
