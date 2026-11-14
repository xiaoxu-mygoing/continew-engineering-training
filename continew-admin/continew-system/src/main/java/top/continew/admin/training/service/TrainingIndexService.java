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

import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import top.continew.starter.core.exception.BusinessException;

import jakarta.annotation.PreDestroy;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

/**
 * 单实例后台索引队列。重启会继续处理数据库里的待办版本。
 *
 * @author 工程实训小组
 * @since 4.2.0
 */
@Service
@Slf4j
@RequiredArgsConstructor
class TrainingIndexService {

    private final JdbcTemplate jdbc;
    private final ObjectMapper mapper;
    private final TrainingRagWorker worker;
    private final TrainingDocumentService documents;
    private final ScheduledExecutorService queue = Executors.newSingleThreadScheduledExecutor();

    @EventListener(ApplicationReadyEvent.class)
    void start() {
        if (worker.configured()) {
            queue.scheduleWithFixedDelay(this::poll, 1, 2, TimeUnit.SECONDS);
        }
    }

    @PreDestroy
    void stop() {
        queue.shutdownNow();
    }

    private record Job(String id, int version, String name, byte[] file) {
    }

    private void poll() {
        try {
            var jobs = jdbc.query(
                "SELECT id, version, file_name, file_content FROM training_document"
                    + " WHERE index_state = 'pending' ORDER BY updated_at, id LIMIT 1",
                (r, i) -> new Job(r.getString(1), r.getInt(2), r.getString(3), r.getBytes(4)));
            if (!jobs.isEmpty()) {
                index(jobs.get(0));
            }
        } catch (RuntimeException e) {
            log.warn("本地索引队列暂时不可用");
        }
    }

    private void index(Job job) {
        String state = "ready";
        String error = null;
        try {
            worker.run(mapper.createObjectNode().put("op", "index").put("documentId", job.id())
                .put("version", job.version()).put("fileName", job.name()).put("file", job.file()),
                900);
        } catch (RuntimeException e) {
            if (Thread.currentThread().isInterrupted()) {
                return;
            }
            state = "failed";
            error = e instanceof BusinessException ? e.getMessage() : "索引失败，请重试";
        }
        int changed = jdbc.update("UPDATE training_document SET index_state = ?, index_error = ?"
            + " WHERE id = ? AND version = ? AND index_state = 'pending'", state, error, job.id(),
            job.version());
        if (changed == 0) {
            documents.discardIndex(job.id(), job.version());
        }
    }
}
