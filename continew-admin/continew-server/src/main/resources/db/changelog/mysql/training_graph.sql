-- liquibase formatted sql

-- changeset training:graph-index-1 dbms:mysql
ALTER TABLE training_document ADD COLUMN graph_state VARCHAR(12) NOT NULL DEFAULT 'pending';
ALTER TABLE training_document ADD COLUMN graph_error VARCHAR(240);
CREATE INDEX idx_training_document_graph_queue ON training_document(graph_state, updated_at);

-- changeset training:graph-cleanup-1 dbms:mysql
CREATE TABLE training_graph_cleanup (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    document_id VARCHAR(36) NOT NULL,
    version INTEGER NOT NULL
);

-- changeset training:graph-build-mode-1 dbms:mysql
ALTER TABLE training_document ADD COLUMN build_mode VARCHAR(12) NOT NULL DEFAULT 'both';
UPDATE training_document SET graph_state = 'pending', graph_error = NULL;
