-- liquibase formatted sql

-- changeset training:face-login-1 dbms:postgresql
UPDATE sys_client SET auth_type = (auth_type::jsonb || '["FACE"]'::jsonb)::json
WHERE client_id = 'ef51c9a3e9046c4f2ea45142c8a8344a' AND NOT (auth_type::jsonb @> '["FACE"]'::jsonb);
