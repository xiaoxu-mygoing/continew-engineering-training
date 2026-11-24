/*
 * Copyright (c) 2022-present Charles7c Authors. All Rights Reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package top.continew.admin.training.service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;
import top.continew.starter.core.exception.BusinessException;
import top.continew.starter.extension.tenant.context.TenantContextHolder;

import jakarta.annotation.PreDestroy;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDateTime;
import java.util.List;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

/**
 * Accounts and retired document versions leave durable cleanup jobs in the application database.
 *
 * @author 工程实训小组
 * @since 4.2.0
 */
@Service
@Slf4j
@RequiredArgsConstructor
public class TrainingPrivacyCleanupService {

    private final JdbcTemplate jdbc;
    private final FaceRecognitionService face;
    private final ScheduledExecutorService faceQueue = Executors.newSingleThreadScheduledExecutor();
    @Value("${TRAINING_RAG_HOME:}")
    private String ragHome;

    private record DocumentVersion(String id, int version) {
    }

    private record VectorJob(long id, String documentId, int version) {
    }

    private record FaceJob(long id, long tenant, long user) {
    }

    /**
     * Serialize enrollment or upload with deletion of the same account.
     *
     * @param user authenticated account ID
     */
    @Transactional(propagation = Propagation.MANDATORY)
    public void requireActiveAccount(long user) {
        Boolean active =
            jdbc.query("SELECT id FROM sys_user WHERE id = ? AND deleted = 0 FOR UPDATE",
                rs -> {
                    return rs.next();
                }, user);
        if (!Boolean.TRUE.equals(active)) {
            throw new BusinessException("账号已删除，请重新登录");
        }
    }

    /**
     * Remove private document rows and schedule cleanup inside the account deletion transaction.
     *
     * @param users validated account IDs that have just been deleted
     */
    @Transactional(propagation = Propagation.MANDATORY)
    public void removeAccounts(List<Long> users) {
        long tenant =
            TenantContextHolder.isTenantEnabled() ? TenantContextHolder.getTenantId() : 0L;
        for (long user : users) {
            var documents = jdbc.query(
                "SELECT id, version FROM training_document WHERE tenant_id = ? AND owner_id = ? FOR UPDATE",
                (row, index) -> new DocumentVersion(row.getString(1), row.getInt(2)), tenant, user);
            for (DocumentVersion doc : documents) {
                enqueueVector(doc.id(), doc.version());
                enqueueGraph(doc.id(), doc.version());
            }
            jdbc.update("DELETE FROM training_document WHERE tenant_id = ? AND owner_id = ?",
                tenant, user);
            jdbc.update("INSERT INTO training_face_cleanup (tenant_id, user_id) VALUES (?, ?)",
                tenant, user);
        }
    }

    void enqueueVector(String id, int version) {
        jdbc.update("INSERT INTO training_vector_cleanup (document_id, version) VALUES (?, ?)", id,
            version);
    }

    void enqueueGraph(String id, int version) {
        jdbc.update("INSERT INTO training_graph_cleanup (document_id, version) VALUES (?, ?)", id,
            version);
    }

    boolean vectorsConfigured() {
        return !ragHome.isBlank();
    }

    // Runs in the vector index writer's queue, so a late index build cannot race cleanup.
    void purgeVectorJobs() {
        if (!vectorsConfigured()) {
            return;
        }
        var jobs = jdbc.query("SELECT id, document_id, version FROM training_vector_cleanup"
            + " WHERE next_attempt_at <= CURRENT_TIMESTAMP ORDER BY next_attempt_at, id LIMIT 10",
            (row, index) -> new VectorJob(row.getLong(1), row.getString(2), row.getInt(3)));
        for (VectorJob job : jobs) {
            try {
                if (!job.documentId().matches("[0-9a-f-]{36}") || job.version() < 1) {
                    throw new IOException("Invalid retired index reference");
                }
                Path path =
                    Path.of(ragHome, "index", job.documentId() + "-v" + job.version() + ".sqlite3");
                Files.deleteIfExists(path);
                for (String suffix : List.of("-journal", "-wal", "-shm")) {
                    Files.deleteIfExists(path.resolveSibling(path.getFileName() + suffix));
                }
                jdbc.update("DELETE FROM training_vector_cleanup WHERE id = ?", job.id());
            } catch (IOException | SecurityException e) {
                jdbc.update("UPDATE training_vector_cleanup SET next_attempt_at = ? WHERE id = ?",
                    LocalDateTime.now().plusSeconds(15), job.id());
                log.warn("旧版向量索引暂时无法清理，等待重试");
            }
        }
    }

    @EventListener(ApplicationReadyEvent.class)
    void start() {
        if (face.cleanupConfigured()) {
            faceQueue.scheduleWithFixedDelay(this::purgeFaceJobs, 3, 2, TimeUnit.SECONDS);
        }
    }

    @PreDestroy
    void stop() {
        faceQueue.shutdownNow();
    }

    private void purgeFaceJobs() {
        try {
            var jobs = jdbc.query("SELECT id, tenant_id, user_id FROM training_face_cleanup"
                + " WHERE next_attempt_at <= CURRENT_TIMESTAMP ORDER BY next_attempt_at, id LIMIT 5",
                (row, index) -> new FaceJob(row.getLong(1), row.getLong(2), row.getLong(3)));
            for (FaceJob job : jobs) {
                try {
                    face.purge(job.tenant(), job.user());
                    jdbc.update("DELETE FROM training_face_cleanup WHERE id = ?", job.id());
                } catch (BusinessException e) {
                    jdbc.update("UPDATE training_face_cleanup SET next_attempt_at = ? WHERE id = ?",
                        LocalDateTime.now().plusSeconds(15), job.id());
                    log.warn("人脸模板暂时无法清理，等待重试");
                }
            }
        } catch (RuntimeException e) {
            log.warn("人脸清理队列暂时不可用");
        }
    }
}
