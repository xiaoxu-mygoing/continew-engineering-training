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

package top.continew.admin.training.controller;

import cn.dev33.satoken.annotation.SaCheckLogin;
import com.fasterxml.jackson.databind.JsonNode;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;
import top.continew.admin.training.service.TrainingDocumentService;
import top.continew.admin.training.service.TrainingDocumentService.DocumentInfo;
import top.continew.admin.training.service.TrainingQuestionService;
import top.continew.starter.log.annotation.Log;

import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.List;

/**
 * 当前登录用户的实训资料接口。
 *
 * @author 工程实训小组
 * @since 4.2.0
 */
@SaCheckLogin
@Log(ignore = true)
@RestController
@RequiredArgsConstructor
@RequestMapping("/training/documents")
public class TrainingDocumentController {

    private final TrainingDocumentService service;
    private final TrainingQuestionService questions;

    public record AskRequest(int version, String question) {
    }

    @PostMapping("/{id}/ask")
    public JsonNode ask(@PathVariable String id, @RequestBody AskRequest input,
        HttpServletResponse response) {
        response.setHeader(HttpHeaders.CACHE_CONTROL, "private, no-store");
        return questions.ask(id, input.version(), input.question());
    }

    @PostMapping("/ask")
    public JsonNode askLibrary(@RequestBody AskRequest input, HttpServletResponse response) {
        response.setHeader(HttpHeaders.CACHE_CONTROL, "private, no-store");
        return questions.ask(null, 0, input.question());
    }

    @PostMapping("/{id}/index")
    public void retry(@PathVariable String id, @RequestParam int version) {
        service.retry(id, version);
    }

    @GetMapping
    public List<DocumentInfo> list() {
        return service.list();
    }

    @PostMapping
    public String create(@RequestPart MultipartFile file,
        @RequestParam(defaultValue = "both") String mode) throws IOException {
        return service.create(file, mode);
    }

    @PutMapping("/{id}")
    public void replace(@PathVariable String id, @RequestParam int version,
        @RequestPart MultipartFile file, @RequestParam(required = false) String mode)
        throws IOException {
        service.replace(id, version, file, mode);
    }

    /**
     * 通过权限和版本检查后，返回禁止缓存的文件内容。
     *
     * @param id 资料编号
     * @param version 请求版本
     * @param response 下载响应
     * @throws IOException 响应写入失败
     */
    @GetMapping("/{id}/content")
    public void read(@PathVariable String id, @RequestParam int version,
        HttpServletResponse response)
        throws IOException {
        byte[] content = service.read(id, version);
        response.setHeader(HttpHeaders.CACHE_CONTROL, "private, no-store");
        response.setHeader(HttpHeaders.CONTENT_DISPOSITION, "attachment");
        response.setHeader("X-Content-Type-Options", "nosniff");
        response.setContentType(MediaType.APPLICATION_OCTET_STREAM_VALUE);
        response.setContentLength(content.length);
        response.getOutputStream().write(content);
        response.flushBuffer();
    }

    @DeleteMapping("/{id}")
    public void delete(@PathVariable String id, @RequestParam int version) {
        service.delete(id, version);
    }
}
