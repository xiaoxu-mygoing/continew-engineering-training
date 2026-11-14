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
import cn.dev33.satoken.stp.StpUtil;
import com.fasterxml.jackson.databind.JsonNode;
import lombok.RequiredArgsConstructor;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import top.continew.admin.common.context.UserContextHolder;
import top.continew.admin.common.util.SecureUtils;
import top.continew.admin.system.model.entity.user.UserDO;
import top.continew.admin.system.service.UserService;
import top.continew.admin.training.service.FaceRecognitionService;
import top.continew.starter.core.exception.BusinessException;
import top.continew.starter.extension.tenant.context.TenantContextHolder;
import top.continew.starter.log.annotation.Log;
import top.continew.starter.ratelimiter.annotation.RateLimiter;
import top.continew.starter.ratelimiter.enums.LimitType;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.PositiveOrZero;
import jakarta.validation.constraints.Size;
import java.util.concurrent.TimeUnit;

/**
 * 本人登录凭据管理。
 *
 * @author 工程实训小组
 * @since 4.2.0
 */
@SaCheckLogin
@Log(ignore = true)
@RestController
@RequestMapping("/user/face")
@RequiredArgsConstructor
public class UserFaceController {

    private final FaceRecognitionService recognition;
    private final PasswordEncoder encoder;
    private final UserService users;

    public record Change(@NotBlank @Size(max = 256) String password,
        @NotNull @PositiveOrZero Long version,
        @Size(max = 450000) String image) {
    }

    @GetMapping
    public JsonNode status() {
        return recognition.run("status", tenant(), StpUtil.getLoginIdAsLong(), 0, null);
    }

    public record Sample(@NotBlank @Size(max = 450000) String image) {
    }

    @PostMapping("/quality")
    @RateLimiter(name = "training:face:quality", rate = 40, interval = 1, unit = TimeUnit.MINUTES,
        type = LimitType.IP)
    public JsonNode quality(@RequestBody @Valid Sample sample) {
        return recognition.run("quality", tenant(), StpUtil.getLoginIdAsLong(), 0, sample.image());
    }

    @PutMapping
    @RateLimiter(name = "training:face:bind", rate = 8, interval = 1, unit = TimeUnit.MINUTES,
        type = LimitType.IP)
    public JsonNode bind(@RequestBody @Valid Change change) {
        return change("bind", change);
    }

    @PutMapping("/identification/{enabled}")
    @RateLimiter(name = "training:face:identification", rate = 8, interval = 1,
        unit = TimeUnit.MINUTES, type = LimitType.IP)
    public JsonNode identification(@PathVariable boolean enabled,
        @RequestBody @Valid Change change) {
        return change(enabled ? "enable" : "disable", change);
    }

    @DeleteMapping
    @RateLimiter(name = "training:face:unbind", rate = 8, interval = 1, unit = TimeUnit.MINUTES,
        type = LimitType.IP)
    public JsonNode unbind(@RequestBody @Valid Change change) {
        return change("unbind", change);
    }

    private JsonNode change(String operation, Change change) {
        long id = StpUtil.getLoginIdAsLong();
        UserDO user = users.getById(id);
        String password = SecureUtils.decryptPasswordByRsaPrivateKey(change.password(), "密码验证失败");
        if (user == null || user.getPassword() == null
            || !encoder.matches(password, user.getPassword())) {
            throw new BusinessException("当前账号密码不正确");
        }
        return recognition.run(operation, tenant(), id, change.version(), change.image());
    }

    private Long tenant() {
        return TenantContextHolder.isTenantEnabled()
            ? UserContextHolder.getExtraContext().getTenantId() : Long.valueOf(0L);
    }
}
