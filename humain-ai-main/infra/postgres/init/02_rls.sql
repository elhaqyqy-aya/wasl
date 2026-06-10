-- 02_rls.sql: Configure Row-Level Security (RLS)

-- Enable RLS on sensitive tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE employees ENABLE ROW LEVEL SECURITY;
ALTER TABLE absences ENABLE ROW LEVEL SECURITY;
ALTER TABLE generated_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE annual_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

-- Helper functions to fetch current context from session settings
CREATE OR REPLACE FUNCTION current_user_id() RETURNS UUID AS $$
    SELECT NULLIF(current_setting('app.current_user_id', true), '')::UUID;
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION current_user_role() RETURNS VARCHAR AS $$
    SELECT current_setting('app.current_user_role', true)::VARCHAR;
$$ LANGUAGE sql STABLE;

-- 1. Policies for `users` table
CREATE POLICY user_all_policy ON users
    FOR ALL
    USING (
        current_user_role() IN ('admin', 'rh', 'direction') OR
        id = current_user_id() OR
        manager_id = current_user_id()
    );

-- 2. Policies for `employees` table
CREATE POLICY employee_all_policy ON employees
    FOR ALL
    USING (
        current_user_role() IN ('admin', 'rh', 'direction') OR
        user_id = current_user_id() OR
        department_id IN (
            SELECT department_id FROM users WHERE id = current_user_id() AND role = 'manager'
        )
    );

-- 3. Policies for `absences` table
CREATE POLICY absence_all_policy ON absences
    FOR ALL
    USING (
        current_user_role() IN ('admin', 'rh', 'direction') OR
        employee_id IN (
            SELECT id FROM employees WHERE user_id = current_user_id()
        ) OR
        employee_id IN (
            SELECT id FROM employees WHERE department_id IN (
                SELECT department_id FROM users WHERE id = current_user_id() AND role = 'manager'
            )
        )
    );

-- 4. Policies for `generated_documents` table
CREATE POLICY document_all_policy ON generated_documents
    FOR ALL
    USING (
        current_user_role() IN ('admin', 'rh') OR
        employee_id IN (
            SELECT id FROM employees WHERE user_id = current_user_id()
        )
    );

-- 5. Policies for `annual_reviews` table
CREATE POLICY review_all_policy ON annual_reviews
    FOR ALL
    USING (
        current_user_role() IN ('admin', 'rh', 'direction') OR
        reviewer_id = current_user_id() OR
        employee_id IN (
            SELECT id FROM employees WHERE user_id = current_user_id()
        )
    );

-- 6. Policies for `audit_logs` table (Only readable by Admin)
CREATE POLICY audit_read_policy ON audit_logs
    FOR SELECT
    USING (current_user_role() = 'admin');

CREATE POLICY audit_write_policy ON audit_logs
    FOR INSERT
    WITH CHECK (TRUE);  -- Anyone can insert audit logs via the system logger
