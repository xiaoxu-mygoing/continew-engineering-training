-- liquibase formatted sql

-- changeset training:face-login-1 dbms:mysql
UPDATE sys_client SET auth_type = JSON_ARRAY_APPEND(auth_type, '$', 'FACE')
WHERE client_id = 'ef51c9a3e9046c4f2ea45142c8a8344a' AND JSON_CONTAINS(auth_type, '"FACE"') = 0;
