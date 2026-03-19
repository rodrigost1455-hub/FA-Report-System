# FA Report Automation System
## Yazaki Electronics Durango — Laboratorio de Análisis de Fallas

Automatización de reportes PDF de análisis de fallas usando el template
original del documento FA_BEC_2 (PHEV BEC GEN 4).

---

## Stack

| Capa       | Tecnología                         |
|------------|------------------------------------|
| Backend    | Python 3.11 + FastAPI              |
| PDF Engine | PyMuPDF (fitz)                     |
| Imágenes   | Pillow                             |
| Base datos | PostgreSQL 15 (Supabase)           |
| Storage    | Supabase Storage                   |
| Frontend   | Next.js 14 + TypeScript (fase 2)   |
| Deploy     | Railway (backend) + Vercel (front) |

---

## Setup inicial

### 1. Clonar y entrar al directorio
```bash
git clone <repo>
cd fa-report-system/backend
```

### 2. Instalar dependencias
```bash
pip install poetry
poetry install
```

### 3. Variables de entorno
```bash
cp .env.example .env
# Editar .env con:
#   DATABASE_URL=postgresql+asyncpg://...
#   SUPABASE_URL=https://xxx.supabase.co
#   SUPABASE_KEY=eyJh...
#   TEMPLATE_PDF_PATH=/ruta/absoluta/a/FA_BEC_2.pdf
```

### 4. Copiar el PDF template
```bash
mkdir -p app/pdf_engine/templates
cp /ruta/a/FA_BEC_2.pdf app/pdf_engine/templates/FA_BEC_2.pdf
```

### 5. Crear schema en Supabase
En el SQL Editor de Supabase, ejecutar en orden:
```sql
-- 1. Schema
\i migrations/001_initial_schema.sql

-- 2. Seed (catálogo de pruebas + usuarios)
\i migrations/002_seed_data.sql
```

### 6. Verificar coordenadas del PDF
**PASO CRÍTICO** — correr antes de producción:
```bash
poetry run python scripts/verify_coordinates.py \
    --pdf app/pdf_engine/templates/FA_BEC_2.pdf \
    --summary
```
Comparar las coordenadas reportadas con `app/pdf_engine/pdf_coordinates.json`
y ajustar los valores según lo que reporte PyMuPDF.

Ver `docs/pdf_coordinate_calibration.md` para guía detallada.

### 7. Levantar el servidor
```bash
poetry run uvicorn main:app --reload --port 8000
```
Docs en: http://localhost:8000/docs

---

## Estructura de archivos clave

```
backend/
├── app/
│   ├── pdf_engine/
│   │   ├── engine.py              ← Motor principal PDF
│   │   ├── pdf_coordinates.json   ← Mapa de coordenadas (CALIBRAR)
│   │   ├── image_processor.py     ← Resize de imágenes
│   │   └── templates/
│   │       └── FA_BEC_2.pdf       ← Template ORIGINAL (no modificar)
│   ├── services/
│   │   ├── pdf_service.py         ← Orquestador del motor
│   │   └── image_service.py       ← Upload + proceso de imágenes
│   └── api/routes/                ← Endpoints REST
└── migrations/
    ├── 001_initial_schema.sql     ← Schema completo
    └── 002_seed_data.sql          ← 20 pruebas + usuarios seed
```

---

## Flujo de generación PDF

1. `POST /api/reports` → crear reporte (status: draft)
2. `POST /api/reports/{id}/images` → subir imágenes por sección
3. `POST /api/reports/{id}/test-results` → guardar resultados de pruebas
4. `POST /api/reports/{id}/generate-pdf` → genera el PDF final
5. `GET  /api/reports/{id}/download` → descarga el PDF

---

## Regla crítica del motor PDF

> El PDF template original **NUNCA se modifica**.
> El motor abre una copia del template y **solo inserta** texto e imágenes
> en las coordenadas del mapa. El layout, tipografía, tablas y estructura
> de páginas son intocables.
