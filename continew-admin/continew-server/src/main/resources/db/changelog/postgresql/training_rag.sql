-- liquibase formatted sql

-- changeset training:rag-index-status-1 dbms:postgresql
ALTER TABLE training_document ADD COLUMN index_state VARCHAR(12) NOT NULL DEFAULT 'pending';
ALTER TABLE training_document ADD COLUMN index_error VARCHAR(240);
CREATE INDEX idx_training_document_queue ON training_document(index_state, updated_at);
