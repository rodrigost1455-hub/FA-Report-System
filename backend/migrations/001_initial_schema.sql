-- ============================================================
-- FA Report Automation System — Schema inicial
-- Yazaki Electronics Durango
-- Compatible con Supabase (PostgreSQL 15+)
-- ============================================================

-- Extensiones necesarias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- ENUMS
-- ============================================================

CREATE TYPE report_status AS ENUM ('draft', 'in_progress', 'final', 'archived');
CREATE TYPE test_result_enum AS ENUM ('OK', 'NG', 'pending');
CREATE TYPE check_type_enum AS ENUM ('no_continuity', 'continuity', 'resistance');
CREATE TYPE image_section_enum AS ENUM ('visual_inspection', 'terminal_inspection', 'eol', 'electrical_test');
CREATE TYPE action_enum AS ENUM ('created', 'updated', 'deleted', 'pdf_generated', 'status_changed');

-- ============================================================
-- TABLA: users
-- Personas que interactúan con los reportes (firmas)
-- ============================================================

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    full_name       VARCHAR(120) NOT NULL,
    employee_id     VARCHAR(30) UNIQUE,
    role            VARCHAR(60),                          -- "Lab Engineer", "Quality Manager", etc.
    department      VARCHAR(80),
    email           VARCHAR(120) UNIQUE,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_full_name ON users (full_name);
CREATE INDEX idx_users_active    ON users (is_active);

COMMENT ON TABLE  users              IS 'Personas que firman o participan en los reportes FA';
COMMENT ON COLUMN users.employee_id  IS 'Número de empleado Yazaki, opcional';
COMMENT ON COLUMN users.role         IS 'Cargo o función dentro del laboratorio';

-- ============================================================
-- TABLA: reports
-- Cabecera principal de cada reporte FA
-- ============================================================

CREATE TABLE reports (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Identificación
    report_number       VARCHAR(20) NOT NULL UNIQUE,      -- Ej: "2506-002"
    title               VARCHAR(120) NOT NULL DEFAULT 'Warranty Plant Return',

    -- Fechas
    request_date        DATE NOT NULL,
    completion_date     DATE NOT NULL DEFAULT CURRENT_DATE,  -- Auto al crear

    -- Información de la pieza
    part_name           VARCHAR(120) NOT NULL,             -- Ej: "PHEV BEC GEN 4"
    part_number         VARCHAR(60)  NOT NULL,             -- Ej: "L1M8 10C666 GF"
    yazaki_part_number  VARCHAR(60)  NOT NULL,             -- Ej: "7370-2573-8W"

    -- Firmas (referencias a users, o texto libre si el usuario no está en el sistema)
    prepared_by_id      UUID REFERENCES users(id) ON DELETE SET NULL,
    verified_by_id      UUID REFERENCES users(id) ON DELETE SET NULL,
    requested_by_id     UUID REFERENCES users(id) ON DELETE SET NULL,
    approved_by_id      UUID REFERENCES users(id) ON DELETE SET NULL,

    -- Nombres en texto plano (para cuando no exista el user en BD o se capture manualmente)
    prepared_by_name    VARCHAR(120),
    verified_by_name    VARCHAR(120),
    requested_by_name   VARCHAR(120),
    approved_by_name    VARCHAR(120),

    -- Flags de lógica del wizard
    is_ntf              BOOLEAN NOT NULL DEFAULT FALSE,    -- No Trouble Found
    reuse_images        BOOLEAN NOT NULL DEFAULT FALSE,    -- NTF: reutilizar imágenes anteriores
    source_report_id    UUID REFERENCES reports(id) ON DELETE SET NULL, -- De qué reporte se reutilizan imágenes

    -- Estado
    status              report_status NOT NULL DEFAULT 'draft',

    -- PDF generado
    pdf_url             TEXT,                              -- URL en Supabase Storage
    pdf_generated_at    TIMESTAMPTZ,

    -- Metadatos
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by          UUID REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_reports_number      ON reports (report_number);
CREATE INDEX idx_reports_status      ON reports (status);
CREATE INDEX idx_reports_request_date ON reports (request_date DESC);
CREATE INDEX idx_reports_part_number ON reports (part_number);

COMMENT ON TABLE  reports                 IS 'Cabecera del reporte de análisis de fallas FA';
COMMENT ON COLUMN reports.report_number   IS 'Número único del reporte, ej: 2506-002';
COMMENT ON COLUMN reports.is_ntf          IS 'TRUE = No Trouble Found; afecta flujo de pruebas eléctricas';
COMMENT ON COLUMN reports.source_report_id IS 'Si is_ntf=true y reuse_images=true, apunta al reporte fuente';
COMMENT ON COLUMN reports.pdf_url         IS 'Path en Supabase Storage al PDF final generado';

-- ============================================================
-- TABLA: report_images
-- Imágenes asociadas a un reporte, organizadas por sección y slot
-- ============================================================

CREATE TABLE report_images (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    report_id       UUID NOT NULL REFERENCES reports(id) ON DELETE CASCADE,

    -- Clasificación
    section         image_section_enum NOT NULL,
    slot_key        VARCHAR(60),                          -- Ej: "arrival_1", "eol_tester", "eol_label", "test_5_1_1"
    sort_order      SMALLINT NOT NULL DEFAULT 0,          -- Orden dentro de la sección

    -- Archivo
    file_url        TEXT NOT NULL,                        -- URL en Supabase Storage
    file_name       VARCHAR(255),
    mime_type       VARCHAR(50) DEFAULT 'image/jpeg',
    file_size_bytes INT,

    -- Dimensiones originales (antes de resize)
    orig_width      INT,
    orig_height     INT,

    -- Dimensiones procesadas (después de resize para el PDF)
    proc_width      INT,
    proc_height     INT,

    -- Flags
    is_reused       BOOLEAN NOT NULL DEFAULT FALSE,       -- TRUE si viene de otro reporte (NTF)
    source_image_id UUID REFERENCES report_images(id) ON DELETE SET NULL,

    -- Metadatos
    caption         VARCHAR(255),                         -- Label visible en el PDF
    uploaded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_rimages_report_id  ON report_images (report_id);
CREATE INDEX idx_rimages_section    ON report_images (section);
CREATE INDEX idx_rimages_slot       ON report_images (slot_key);
CREATE INDEX idx_rimages_sort       ON report_images (report_id, section, sort_order);

COMMENT ON TABLE  report_images           IS 'Imágenes adjuntas al reporte, organizadas por sección del PDF';
COMMENT ON COLUMN report_images.slot_key  IS 'Identificador del slot en el PDF: arrival_1..N, eol_tester, eol_label, eol_result, test_5_1_1_left, test_5_1_1_right';
COMMENT ON COLUMN report_images.sort_order IS 'Orden de aparición dentro de la sección visual_inspection';

-- ============================================================
-- TABLA: electrical_tests_catalog
-- Secuencia fija de las 20 pruebas eléctricas del documento
-- Solo se inserta una vez (seed). No se modifica por el usuario.
-- ============================================================

CREATE TABLE electrical_tests_catalog (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code            VARCHAR(20) NOT NULL UNIQUE,          -- "5.1.1", "5.1.2", ... "5.4.5"
    sort_order      SMALLINT NOT NULL,                    -- Orden global de ejecución (1..20)

    -- Jerarquía
    section_num     SMALLINT NOT NULL,                    -- 1=Main Cont(+), 2=Main Cont(-), 3=Aux Cont, 4=PreCharge
    section_title   VARCHAR(120) NOT NULL,                -- "Main Contactor (+) (final checker)"
    sub_code        VARCHAR(20) NOT NULL,                 -- "5.1", "5.2", etc.
    sub_title       VARCHAR(200) NOT NULL,                -- "Verify (+) Main Cont. Normally Open"

    -- Qué se mide
    check_type      check_type_enum NOT NULL,
    terminal_pos    VARCHAR(10),                          -- Terminal positivo o punto A, ej: "A1"
    terminal_neg    VARCHAR(10),                          -- Terminal negativo o punto B, ej: "H1"
    voltage_source  VARCHAR(20),                          -- "12V D1", "12V D3", "12V D4", "12V D6", NULL
    expected_result VARCHAR(80),                          -- "no continuity", "continuity", "27.6Ω ±5%"

    -- Texto descriptivo del sub-paso en el documento
    step_description TEXT,

    -- Dónde aparece en el PDF (para el motor)
    pdf_page        SMALLINT NOT NULL,                    -- Número de página (4..12)
    pdf_position    VARCHAR(10) NOT NULL,                 -- "left" | "right" | "bottom" (posición en la página)

    -- Flag de diseño especial (ej: 5.4 tiene req. de resistencia en rojo)
    has_design_req  BOOLEAN NOT NULL DEFAULT FALSE,
    design_req_text VARCHAR(100),                          -- "(Design requirement, 27.6Ω ±5%)"

    is_active       BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX idx_etcat_sort_order ON electrical_tests_catalog (sort_order);
CREATE INDEX idx_etcat_code       ON electrical_tests_catalog (code);

COMMENT ON TABLE  electrical_tests_catalog IS 'Catálogo fijo de las 20 pruebas eléctricas del documento FA. Solo lectura en producción.';
COMMENT ON COLUMN electrical_tests_catalog.pdf_position IS 'left=imagen izquierda de la página, right=imagen derecha, bottom=imagen única abajo';

-- ============================================================
-- TABLA: test_results
-- Resultados reales de cada prueba para un reporte específico
-- ============================================================

CREATE TABLE test_results (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    report_id       UUID NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    catalog_id      UUID NOT NULL REFERENCES electrical_tests_catalog(id),

    -- Resultado
    result          test_result_enum NOT NULL DEFAULT 'pending',
    measurement_val VARCHAR(40),                          -- Valor medido real, ej: "000034 OHM", "027396 OHM"
    is_ng_override  BOOLEAN NOT NULL DEFAULT FALSE,       -- TRUE si el usuario forzó continuar tras NG

    -- Imagen asociada a esta prueba (foto del tester + pieza)
    image_left_id   UUID REFERENCES report_images(id) ON DELETE SET NULL,
    image_right_id  UUID REFERENCES report_images(id) ON DELETE SET NULL,

    -- Reutilización NTF
    is_reused       BOOLEAN NOT NULL DEFAULT FALSE,
    source_result_id UUID REFERENCES test_results(id) ON DELETE SET NULL,

    -- Texto del bloque de observación en el PDF
    observation_text TEXT DEFAULT 'No anomalies were observed in the manual test.',

    -- Timestamps
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (report_id, catalog_id)                        -- Un resultado por prueba por reporte
);

CREATE INDEX idx_tresults_report_id  ON test_results (report_id);
CREATE INDEX idx_tresults_catalog_id ON test_results (catalog_id);
CREATE INDEX idx_tresults_result     ON test_results (result);

COMMENT ON TABLE  test_results            IS 'Resultados de cada prueba eléctrica para un reporte dado';
COMMENT ON COLUMN test_results.is_ng_override IS 'Si el técnico eligió continuar luego de un NG, este flag queda TRUE';
COMMENT ON COLUMN test_results.measurement_val IS 'Valor crudo leído en el multímetro o tester, como aparece en la foto';

-- ============================================================
-- TABLA: report_audit_log
-- Historial de modificaciones para trazabilidad IATF
-- ============================================================

CREATE TABLE report_audit_log (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    report_id       UUID NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    action          action_enum NOT NULL,
    changed_by_id   UUID REFERENCES users(id) ON DELETE SET NULL,
    changed_by_name VARCHAR(120),                         -- Nombre en texto por si se elimina el user

    -- Qué cambió
    field_name      VARCHAR(80),                          -- Campo modificado, ej: "status", "part_number"
    old_value       TEXT,
    new_value       TEXT,
    extra_data      JSONB,                                -- Datos adicionales del evento (ej: qué prueba resultó NG)

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_report_id  ON report_audit_log (report_id);
CREATE INDEX idx_audit_action     ON report_audit_log (action);
CREATE INDEX idx_audit_created_at ON report_audit_log (created_at DESC);

COMMENT ON TABLE  report_audit_log IS 'Log inmutable de cambios sobre reportes, requerido para trazabilidad IATF 16949';

-- ============================================================
-- FUNCIÓN + TRIGGER: auto-updated_at
-- ============================================================

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_reports_updated_at
    BEFORE UPDATE ON reports
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_tresults_updated_at
    BEFORE UPDATE ON test_results
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================
-- FUNCIÓN: auto-log en audit_log cuando cambia el status
-- ============================================================

CREATE OR REPLACE FUNCTION log_report_status_change()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status IS DISTINCT FROM NEW.status THEN
        INSERT INTO report_audit_log (report_id, action, field_name, old_value, new_value)
        VALUES (NEW.id, 'status_changed', 'status', OLD.status::TEXT, NEW.status::TEXT);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_report_status_log
    AFTER UPDATE ON reports
    FOR EACH ROW EXECUTE FUNCTION log_report_status_change();

-- ============================================================
-- FUNCIÓN: auto-log cuando se genera el PDF
-- ============================================================

CREATE OR REPLACE FUNCTION log_pdf_generated()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.pdf_url IS NULL AND NEW.pdf_url IS NOT NULL THEN
        INSERT INTO report_audit_log (report_id, action, new_value)
        VALUES (NEW.id, 'pdf_generated', NEW.pdf_url);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_pdf_generated_log
    AFTER UPDATE ON reports
    FOR EACH ROW EXECUTE FUNCTION log_pdf_generated();

-- ============================================================
-- VIEW: reports_summary
-- Vista de búsqueda para el historial de reportes
-- ============================================================

CREATE VIEW reports_summary AS
SELECT
    r.id,
    r.report_number,
    r.title,
    r.request_date,
    r.completion_date,
    r.part_name,
    r.part_number,
    r.yazaki_part_number,
    r.status,
    r.is_ntf,
    r.pdf_url,
    r.pdf_generated_at,
    COALESCE(r.prepared_by_name,  up.full_name)  AS prepared_by,
    COALESCE(r.verified_by_name,  uv.full_name)  AS verified_by,
    COALESCE(r.requested_by_name, ur.full_name)  AS requested_by,
    COALESCE(r.approved_by_name,  ua.full_name)  AS approved_by,
    -- Conteo de pruebas
    (SELECT COUNT(*) FROM test_results tr WHERE tr.report_id = r.id)                                AS total_tests,
    (SELECT COUNT(*) FROM test_results tr WHERE tr.report_id = r.id AND tr.result = 'OK')          AS tests_ok,
    (SELECT COUNT(*) FROM test_results tr WHERE tr.report_id = r.id AND tr.result = 'NG')          AS tests_ng,
    (SELECT COUNT(*) FROM test_results tr WHERE tr.report_id = r.id AND tr.result = 'pending')     AS tests_pending,
    -- Conteo de imágenes
    (SELECT COUNT(*) FROM report_images ri WHERE ri.report_id = r.id)                              AS total_images,
    r.created_at,
    r.updated_at
FROM reports r
LEFT JOIN users up ON r.prepared_by_id  = up.id
LEFT JOIN users uv ON r.verified_by_id  = uv.id
LEFT JOIN users ur ON r.requested_by_id = ur.id
LEFT JOIN users ua ON r.approved_by_id  = ua.id;

COMMENT ON VIEW reports_summary IS 'Vista desnormalizada para listado y búsqueda de reportes';
