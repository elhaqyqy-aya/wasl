-- 03_seed.sql: Seed initial site, department, position, user, and employee data

-- 1. Seed Sites
INSERT INTO sites (id, name, location) VALUES
('b3b3b3b3-b3b3-b3b3-b3b3-b3b3b3b3b3b3', 'Paris Campus', 'Paris, France'),
('c4c4c4c4-c4c4-c4c4-c4c4-c4c4c4c4c4c4', 'Casablanca Campus', 'Casablanca, Morocco')
ON CONFLICT (id) DO NOTHING;

-- 2. Seed Departments
INSERT INTO departments (id, name, parent_id, site_id) VALUES
('d1d1d1d1-d1d1-d1d1-d1d1-d1d1d1d1d1d1', 'Direction Générale', NULL, 'b3b3b3b3-b3b3-b3b3-b3b3-b3b3b3b3b3b3'),
('d2d2d2d2-d2d2-d2d2-d2d2-d2d2d2d2d2d2', 'Ressources Humaines', 'd1d1d1d1-d1d1-d1d1-d1d1-d1d1d1d1d1d1', 'b3b3b3b3-b3b3-b3b3-b3b3-b3b3b3b3b3b3'),
('d3d3d3d3-d3d3-d3d3-d3d3-d3d3d3d3d3d3', 'Développement Tech', 'd1d1d1d1-d1d1-d1d1-d1d1-d1d1d1d1d1d1', 'c4c4c4c4-c4c4-c4c4-c4c4-c4c4c4c4c4c4')
ON CONFLICT (id) DO NOTHING;

-- 3. Seed Positions
INSERT INTO positions (id, name) VALUES
('p1p1p1p1-p1p1-p1p1-p1p1-p1p1p1p1p1p1', 'Directeur Général'),
('p2p2p2p2-p2p2-p2p2-p2p2-p2p2p2p2p2p2', 'Responsable RH'),
('p3p3p3p3-p3p3-p3p3-p3p3-p3p3p3p3p3p3', 'Lead Tech DevOps'),
('p4p4p4p4-p4p4-p4p4-p4p4-p4p4p4p4p4p4', 'Développeur Fullstack')
ON CONFLICT (id) DO NOTHING;

-- 4. Seed Users
-- Passwords and authentications are handled via Firebase Auth.
-- These matching database entries correspond to Firebase UIDs.
INSERT INTO users (id, firebase_uid, email, display_name, role, department_id, manager_id, is_active) VALUES
('u1111111-1111-1111-1111-111111111111', 'fb-uid-admin', 'admin@humanai.com', 'Admin System', 'admin', NULL, NULL, TRUE),
('u2222222-2222-2222-2222-222222222222', 'fb-uid-hr', 'rh@humanai.com', 'Sarah RH', 'rh', 'd2d2d2d2-d2d2-d2d2-d2d2-d2d2d2d2d2d2', NULL, TRUE),
('u3333333-3333-3333-3333-333333333333', 'fb-uid-manager', 'manager@humanai.com', 'Jean Tech Manager', 'manager', 'd3d3d3d3-d3d3-d3d3-d3d3-d3d3d3d3d3d3', NULL, TRUE),
('u4444444-4444-4444-4444-444444444444', 'fb-uid-collab', 'collab@humanai.com', 'Alex Dev', 'collaborateur', 'd3d3d3d3-d3d3-d3d3-d3d3-d3d3d3d3d3d3', 'u3333333-3333-3333-3333-333333333333', TRUE)
ON CONFLICT (id) DO NOTHING;

-- 5. Seed Employees
INSERT INTO employees (id, user_id, matricule, full_name, position_id, department_id, hire_date, contract_type, salary_band, status, sirh_sync_id) VALUES
('e1111111-1111-1111-1111-111111111111', 'u1111111-1111-1111-1111-111111111111', 'MAT-0001', 'Admin System', 'p1p1p1p1-p1p1-p1p1-p1p1-p1p1p1p1p1p1', 'd1d1d1d1-d1d1-d1d1-d1d1-d1d1d1d1d1d1', '2025-01-01', 'cdi', NULL, 'actif', 'SIRH-001'),
('e2222222-2222-2222-2222-222222222222', 'u2222222-2222-2222-2222-222222222222', 'MAT-0002', 'Sarah RH', 'p2p2p2p2-p2p2-p2p2-p2p2-p2p2p2p2p2p2', 'd2d2d2d2-d2d2-d2d2-d2d2-d2d2d2d2d2d2', '2025-02-15', 'cdi', NULL, 'actif', 'SIRH-002'),
('e3333333-3333-3333-3333-333333333333', 'u3333333-3333-3333-3333-333333333333', 'MAT-0003', 'Jean Tech Manager', 'p3p3p3p3-p3p3-p3p3-p3p3-p3p3p3p3p3p3', 'd3d3d3d3-d3d3-d3d3-d3d3-d3d3d3d3d3d3', '2025-03-01', 'cdi', NULL, 'actif', 'SIRH-003'),
('e4444444-4444-4444-4444-444444444444', 'u4444444-4444-4444-4444-444444444444', 'MAT-0004', 'Alex Dev', 'p4p4p4p4-p4p4-p4p4-p4p4-p4p4p4p4p4p4', 'd3d3d3d3-d3d3-d3d3-d3d3-d3d3d3d3d3d3', '2025-04-10', 'cdi', NULL, 'actif', 'SIRH-004')
ON CONFLICT (id) DO NOTHING;

-- 6. Seed Document Templates
INSERT INTO document_templates (id, name, type, content_template, allowed_roles) VALUES
('t1111111-1111-1111-1111-111111111111', 'Attestation d''emploi standard', 'attestation', 'Je soussigné, Direction Générale, atteste que {{full_name}} est employé(e) au sein de notre entreprise.', '{"admin", "rh", "manager", "collaborateur"}'),
('t2222222-2222-2222-2222-222222222222', 'Lettre de départ / Clôture', 'offboarding', 'Clôture de contrat pour {{full_name}} effectif au {{departure_date}}.', '{"admin", "rh"}')
ON CONFLICT (id) DO NOTHING;
