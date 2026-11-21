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
import com.fasterxml.jackson.databind.node.ObjectNode;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import top.continew.starter.core.exception.BusinessException;

import java.io.IOException;
import java.io.OutputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.concurrent.Semaphore;
import java.util.concurrent.TimeUnit;

/**
 * 调用仅通过标准输入接收数据的本地识别程序。
 *
 * @author 工程实训小组
 * @since 4.2.0
 */
@Service
@RequiredArgsConstructor
public class FaceRecognitionService {

    private final ObjectMapper mapper;
    private final Semaphore workers = new Semaphore(2);
    @Value("${TRAINING_FACE_HOME:}")
    private String home;
    @Value("${TRAINING_FACE_WORKER:}")
    private String script;

    /**
     * 执行指定账号的模板操作。
     *
     * @param operation 操作
     * @param tenant 服务端租户编号
     * @param user 服务端用户编号
     * @param version 预期模板版本
     * @param image 摄像头采集帧
     * @return 状态或比对结果
     */
    public JsonNode run(String operation, Long tenant, long user, long version, String image) {
        ObjectNode req = mapper.createObjectNode().put("op", operation)
            .put("tenant", tenant).put("user", user).put("version", version).put("image", image);
        return execute(req, tenant, 15);
    }

    /**
     * 验证服务端指定的动作与连续采集帧。
     *
     * @param req 活体采集内容
     * @param tenant 当前租户
     * @return 活体判定
     * @since 4.2.0
     */
    public JsonNode liveness(ObjectNode req, Long tenant) {
        req.put("op", "liveness");
        return execute(req, tenant, 60);
    }

    private JsonNode execute(ObjectNode req, Long tenant, int timeoutSeconds) {
        if (tenant == null || home.isBlank() || script.isBlank()
            || !Files.isRegularFile(Path.of(script))) {
            throw new BusinessException("本地人脸识别服务未就绪，请使用密码登录");
        }
        if (!workers.tryAcquire()) {
            throw new BusinessException("识别服务繁忙，请稍后重试");
        }
        Process process = null;
        try {
            Path python = Path.of(home, "venv", "Scripts", "python.exe");
            ProcessBuilder builder =
                new ProcessBuilder(python.toString(), "-I", "-B", "-X", "utf8", script);
            builder.environment().put("TRAINING_FACE_HOME", home);
            builder.redirectError(ProcessBuilder.Redirect.DISCARD);
            process = builder.start();
            try (OutputStream input = process.getOutputStream()) {
                mapper.writeValue(input, req);
            }
            if (!process.waitFor(timeoutSeconds, TimeUnit.SECONDS) || process.exitValue() != 0) {
                throw new BusinessException("识别服务未响应，请稍后重试");
            }
            JsonNode result = mapper.readTree(process.getInputStream());
            if (result == null || !result.path("data").isObject()) {
                throw new BusinessException(
                    result == null ? "识别服务不可用" : result.path("error").asText("识别失败"));
            }
            return result.get("data");
        } catch (IOException e) {
            throw new BusinessException("无法启动或访问本地识别服务，请使用密码登录");
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new BusinessException("识别请求已中断");
        } finally {
            if (process != null) {
                process.destroyForcibly();
            }
            workers.release();
        }
    }
}
