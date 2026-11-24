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

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import top.continew.admin.training.service.TrainingDocumentService.DocumentInfo;
import top.continew.starter.core.exception.BusinessException;

import java.util.List;
import java.util.concurrent.Semaphore;

/**
 * 检索当前账号有权读取的已就绪资料。
 *
 * @author 工程实训小组
 * @since 4.2.0
 */
@Service
@RequiredArgsConstructor
public class TrainingQuestionService {

    private final TrainingDocumentService documents;
    private final TrainingRagWorker worker;
    private final ObjectMapper mapper;
    private final Semaphore slot = new Semaphore(1);

    /**
     * 针对单份资料或整个个人资料库提问。
     *
     * @param id 资料编号，空表示个人资料库
     * @param version 文件版本
     * @param question 问题
     * @return 答案和来源
     */
    public JsonNode ask(String id, int version, String question) {
        return retrieve(id, version, question, false);
    }

    public JsonNode search(String query) {
        return retrieve(null, 0, query, true);
    }

    private JsonNode retrieve(String id, int version, String question, boolean searchOnly) {
        if (question == null || question.isBlank() || question.length() > 500) {
            throw new BusinessException("请输入 1 至 500 字的内容");
        }
        List<DocumentInfo> available = documents.list();
        if (id != null) {
            available = available.stream()
                .filter(d -> d.documentId().equals(id) && d.version() == version).toList();
            if (available.isEmpty()) {
                throw new BusinessException("资料不可访问或版本已更新，请刷新列表");
            }
        }
        boolean allowGeneral = id == null && !searchOnly;
        var req = mapper.createObjectNode().put("op", searchOnly ? "search" : "ask")
            .put("question", question.trim()).put("allowGeneral", allowGeneral);
        var ready = req.putArray("documents");
        for (DocumentInfo doc : available) {
            if ("ready".equals(doc.indexState())) {
                ready.addObject().put("documentId", doc.documentId()).put("version", doc.version())
                    .put("fileName", doc.fileName());
            }
        }
        if (ready.isEmpty() && !allowGeneral) {
            if (searchOnly) {
                var empty = mapper.createObjectNode();
                empty.putArray("results");
                return empty;
            }
            throw new BusinessException("暂无可问答的资料，请查看索引状态");
        }
        if (!slot.tryAcquire()) {
            throw new BusinessException("本地问答正在处理其他问题，请稍后重试");
        }
        try {
            int timeout = allowGeneral ? 255 : 210;
            JsonNode answer = worker.run(req, searchOnly ? 75 : timeout);
            for (JsonNode source : answer.path(searchOnly ? "results" : "sources")) {
                documents.currentName(source.path("documentId").asText(),
                    source.path("version").asInt());
            }
            if (id != null) {
                documents.currentName(id, version);
            }
            return answer;
        } finally {
            slot.release();
        }
    }
}
