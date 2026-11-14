-- liquibase formatted sql

-- changeset training:private-documents-1 dbms:postgresql
CREATE TABLE training_document (
    id VARCHAR(36) PRIMARY KEY,
    tenant_id BIGINT NOT NULL,
    owner_id BIGINT NOT NULL,
    version INTEGER NOT NULL,
    file_name VARCHAR(180) NOT NULL,
    file_size INTEGER NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    file_content BYTEA NOT NULL
);
CREATE INDEX idx_training_document_owner ON training_document (tenant_id, owner_id, updated_at);
