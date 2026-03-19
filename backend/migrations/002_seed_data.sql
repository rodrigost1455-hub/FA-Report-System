-- ============================================================
-- SEED: electrical_tests_catalog
-- Las 20 pruebas eléctricas en secuencia fija extraídas del
-- documento FA_BEC_2.pdf (PHEV BEC GEN 4)
-- ============================================================

INSERT INTO electrical_tests_catalog (
    code, sort_order, section_num, section_title, sub_code, sub_title,
    check_type, terminal_pos, terminal_neg, voltage_source, expected_result,
    step_description, pdf_page, pdf_position,
    has_design_req, design_req_text
) VALUES

-- ============================================================
-- SECCIÓN 5.1 — Main Contactor (+) (final checker)
-- ============================================================
(
    '5.1.1', 1, 1, 'Main Contactor (+) (final checker)',
    '5.1', 'Verify (+) Main Cont. Normally Open',
    'no_continuity', 'A1', 'H1', NULL, 'no continuity',
    'Connect continuity positive to Terminal A1. Connect continuity negative to Terminal H1. Check for no continuity. Read result. (no continuity). Disconnect continuity negative from Terminal H1.',
    4, 'left', FALSE, NULL
),
(
    '5.1.2', 2, 1, 'Main Contactor (+) (final checker)',
    '5.1', 'Verify (+) Main Cont. Closed / Pos HV BUS circuit',
    'continuity', 'A1', 'H1', '12V D1', 'continuity',
    'Attach power supply lead to Ground Terminal D5. Attach power supply lead to Terminal D1 and energize with 12V. Connect continuity negative to Terminal H1. Check for continuity. Read result. (continuity). Disconnect continuity negative from Terminal H1.',
    4, 'right', FALSE, NULL
),
(
    '5.1.3', 3, 1, 'Main Contactor (+) (final checker)',
    '5.1', 'Verify (+) HV BUS Circuit / DCDC/Charge (+) terminal presence',
    'continuity', 'A1', 'E2', '12V D1', 'continuity',
    'Connect continuity negative to Terminal E2. Check for continuity. Read result. (continuity). Disconnect continuity negative from Terminal E2.',
    5, 'left', FALSE, NULL
),
(
    '5.1.4', 4, 1, 'Main Contactor (+) (final checker)',
    '5.1', 'Verify (+) HV BUS Circuit / eAC/PTC (+) terminal presence',
    'continuity', 'A1', 'G1', '12V D1', 'continuity',
    'Connect continuity negative to Terminal G1. Check for continuity. Read result. (continuity). Disconnect continuity negative from Terminal G1.',
    5, 'right', FALSE, NULL
),
(
    '5.1.5', 5, 1, 'Main Contactor (+) (final checker)',
    '5.1', 'Verify (+) HV BUS Circuit / VCONT_POS terminal presence',
    'continuity', 'A1', 'F2', NULL, 'continuity',
    'Connect continuity negative to Terminal F2. Check for continuity. Read result. (continuity). Disconnect continuity negative from Terminal F2.',
    6, 'left', FALSE, NULL
),
(
    '5.1.6', 6, 1, 'Main Contactor (+) (final checker)',
    '5.1', 'Verify (+) Main Cont. Normally Open',
    'no_continuity', 'A1', 'H1', '12V D1', 'no continuity',
    'De-energize terminal D1. Connect continuity negative to Terminal H1. Check for no continuity. Read result. (no continuity). Disconnect all leads except for D5.',
    6, 'right', FALSE, NULL
),

-- ============================================================
-- SECCIÓN 5.2 — Main Contactor (-) (final checker)
-- ============================================================
(
    '5.2.1', 7, 2, 'Main Contactor (-) (final checker)',
    '5.2', 'Verify (-) Main Cont. Normally Open',
    'no_continuity', 'B1', 'I1', NULL, 'no continuity',
    'Connect continuity positive to Terminal B1. Connect continuity negative to Terminal I1. Check for no continuity. Read result. (no continuity). Disconnect continuity negative from Terminal I1.',
    7, 'left', FALSE, NULL
),
(
    '5.2.2', 8, 2, 'Main Contactor (-) (final checker)',
    '5.2', 'Verify (-) Main contactor closed / Neg. HV BUS circuit / Good main fuse',
    'continuity', 'B1', 'I1', '12V D3', 'continuity',
    'Attach power supply lead to Terminal D3 and energize with 12V. Connect continuity negative to Terminal I1. Check for continuity. Read result. (continuity). Disconnect continuity negative from Terminal I1.',
    7, 'right', FALSE, NULL
),
(
    '5.2.3', 9, 2, 'Main Contactor (-) (final checker)',
    '5.2', 'Verify (-) HV BUS circuit / eAC/PTC (-) terminal presence / Good 40A fuse',
    'continuity', 'B1', 'G3', '12V D3', 'continuity',
    'Connect continuity negative to Terminal G3. Check for continuity. Read result. (continuity). Disconnect continuity negative from Terminal G3.',
    8, 'left', FALSE, NULL
),
(
    '5.2.4', 10, 2, 'Main Contactor (-) (final checker)',
    '5.2', 'Verify (-) HV BUS circuit / VCONT_NEG terminal presence / Good 40A fuse',
    'continuity', 'B1', 'K2', '12V D3', 'continuity',
    'Connect continuity negative to Terminal K2. Check for continuity. Read result. (continuity). Disconnect continuity negative from Terminal K2.',
    8, 'right', FALSE, NULL
),
(
    '5.2.5', 11, 2, 'Main Contactor (-) (final checker)',
    '5.2', 'Verify (-) Main Cont. Normally Open',
    'no_continuity', 'B1', 'I1', NULL, 'no continuity',
    'De-energize Terminal D3. Connect continuity negative to Terminal I1. Check for no continuity. Read result. (no continuity). Disconnect all leads except for B1 & D5.',
    8, 'bottom', FALSE, NULL
),

-- ============================================================
-- SECCIÓN 5.3 — Auxiliary Contactor (final checker)
-- ============================================================
(
    '5.3.1', 12, 3, 'Auxiliary Contactor (final checker)',
    '5.3', 'Verify Auxiliary Contactor normally open',
    'no_continuity', 'B1', 'E3', NULL, 'no continuity',
    'Connect continuity negative to terminal E3. Check for no continuity. Read result. (no continuity). Disconnect continuity negative from Terminal E3.',
    9, 'left', FALSE, NULL
),
(
    '5.3.2', 13, 3, 'Auxiliary Contactor (final checker)',
    '5.3', 'Verify (-) HV Auxiliary BUS circuit / DCDC/CHG (-) terminal presence / Good 40A fuse',
    'continuity', 'B1', 'E3', '12V D6', 'continuity',
    'Attach power supply lead to Terminal D6 and energize with 12V. Connect continuity negative to terminal E3. Check for continuity. Read results. (continuity). Disconnect continuity negative from Terminal E3.',
    9, 'right', FALSE, NULL
),
(
    '5.3.3', 14, 3, 'Auxiliary Contactor (final checker)',
    '5.3', 'Verify (-) HV Auxiliary BUS circuit / VCONT_AUX terminal presence',
    'continuity', 'B1', 'J2', '12V D6', 'continuity',
    'Connect continuity negative to Terminal J2. Check for continuity. Read results. (continuity). Disconnect continuity negative from Terminal J2.',
    10, 'left', FALSE, NULL
),
(
    '5.3.4', 15, 3, 'Auxiliary Contactor (final checker)',
    '5.3', 'Verify Auxiliary Contactor normally open',
    'no_continuity', 'B1', 'E3', NULL, 'no continuity',
    'De-energize terminal D6. Connect continuity negative to terminal E3. Check for no continuity. Read result. (no continuity). Disconnect all leads except for D5.',
    10, 'right', FALSE, NULL
),

-- ============================================================
-- SECCIÓN 5.4 — Pre-Charge Contactor (final checker)
-- Design requirement: 27.6Ω ±5%
-- ============================================================
(
    '5.4.1', 16, 4, 'Pre-Charge Contactor (final checker)',
    '5.4', 'Verify Pre-Charge contactor normally open',
    'no_continuity', 'A1', 'E2', NULL, 'no continuity',
    'Connect continuity positive to Terminal A1. Connect continuity negative to Terminal E2. Check for no continuity. Read result. (no continuity). Disconnect continuity negative from Terminal E2.',
    11, 'left', TRUE, '(Design requirement, 27.6Ω ±5%)'
),
(
    '5.4.2', 17, 4, 'Pre-Charge Contactor (final checker)',
    '5.4', 'Verify Pre-Charge circuit / Pre-charge Contactor / Good Resistor',
    'resistance', 'A1', 'H1', '12V D4', 'resistance ~27.6Ω ±5%',
    'Attach power supply lead to Terminal D4 and energize with 12V. Connect resistance lead negative to Terminal H1. Check resistance. Record result. (resistance). Disconnect resistance lead negative from Terminal H1.',
    11, 'right', TRUE, '(Design requirement, 27.6Ω ±5%)'
),
(
    '5.4.3', 18, 4, 'Pre-Charge Contactor (final checker)',
    '5.4', 'Verify Pre-Charge circuit / DCDC/CHG (+) terminal presence',
    'resistance', 'A1', 'E2', '12V D4', 'resistance ~27.6Ω ±5%',
    'Connect resistance lead negative to Terminal E2. Check resistance. Record result. (resistance). Disconnect resistance lead negative from Terminal E2.',
    12, 'left', TRUE, '(Design requirement, 27.6Ω ±5%)'
),
(
    '5.4.4', 19, 4, 'Pre-Charge Contactor (final checker)',
    '5.4', 'Verify Pre-Charge circuit / eAC/PTC (+) terminal presence',
    'resistance', 'A1', 'G1', '12V D4', 'resistance ~27.6Ω ±5%',
    'Connect resistance lead negative to Terminal G1. Check resistance. Record result. (resistance). Disconnect resistance lead negative from Terminal G1.',
    12, 'right', TRUE, '(Design requirement, 27.6Ω ±5%)'
),
(
    '5.4.5', 20, 4, 'Pre-Charge Contactor (final checker)',
    '5.4', 'Verify Pre-charge circuit / VCONT_POS terminal presence',
    'resistance', 'A1', 'F2', '12V D4', 'resistance ~27.6Ω ±5%',
    'Connect resistance lead negative to Terminal F2. Check resistance. Record result. (resistance). De-energize Terminal D4. Disconnect all leads.',
    12, 'bottom', TRUE, '(Design requirement, 27.6Ω ±5%)'
);

-- ============================================================
-- SEED: usuarios default del laboratorio
-- (Editar según plantilla real de Yazaki)
-- ============================================================

INSERT INTO users (full_name, role, department) VALUES
    ('Horacio Martinez', 'Aprobador / Approved',         'Laboratorio FA'),
    ('Juan Barraza',     'Verificador / Checked',         'Laboratorio FA'),
    ('Rodrigo Santana',  'Preparador / Prepared',         'Laboratorio FA'),
    ('Chandni Bhavsar',  'Requisitante / Requestor',      'Calidad / Customer');
