-- liquibase formatted sql

-- changeset training:privacy-cleanup-1 dbms:mysql
CREATE TABLE training_vector_cleanup (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    document_id VARCHAR(36) NOT NULL,
    version INTEGER NOT NULL,
    next_attempt_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_training_vector_cleanup_due ON training_vector_cleanup(next_attempt_at, id);

CREATE TABLE training_face_cleanup (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    tenant_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    next_attempt_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_training_face_cleanup_due ON training_face_cleanup(next_attempt_at, id);
