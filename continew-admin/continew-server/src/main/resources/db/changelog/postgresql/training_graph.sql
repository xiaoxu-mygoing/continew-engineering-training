-- liquibase formatted sql

-- changeset training:graph-index-1 dbms:postgresql
ALTER TABLE training_document ADD COLUMN graph_state VARCHAR(12) NOT NULL DEFAULT 'pending';
ALTER TABLE training_document ADD COLUMN graph_error VARCHAR(240);
CREATE INDEX idx_training_document_graph_queue ON training_document(graph_state, updated_at);

-- changeset training:graph-cleanup-1 dbms:postgresql
CREATE TABLE training_graph_cleanup (
    id BIGSERIAL PRIMARY KEY,
    document_id VARCHAR(36) NOT NULL,
    version INTEGER NOT NULL
);
